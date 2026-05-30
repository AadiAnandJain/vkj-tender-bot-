#!/usr/bin/env python3
"""
VKJ Tender Discovery Bot
Runs via GitHub Actions twice daily: 7AM + 7PM IST
Scrapes tenderdetail.com for active building + railway construction tenders
Target states: Uttarakhand, UP, Himachal, Punjab, Chandigarh + All India EPC/Infra
Value: ₹10-300 Cr (building) · ₹10-500 Cr (railway)
Writes to Firebase: bot_tenders collection (separate from review_queue)
Deduplication: by tender title hash — never duplicated
"""

import urllib.request, ssl, re, json, time, hashlib, os
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────
FB_KEY = "AIzaSyAeAbG_9oNwWNmAzGQR7VgwFiDGNj5-ztg"
FB_PROJECT = "vkj-tender-tacker"
FB_BOT_COL = "bot_tenders"      # Separate collection — NOT review_queue
FB_SEEN_COL = "bot_seen_ids"    # Deduplication store

TARGET_STATES = [
    'uttarakhand', 'uttar pradesh', 'himachal pradesh',
    'himachal', 'punjab', 'chandigarh', 'haryana', 'delhi',
    'uk', 'up', 'hp', 'dehradun', 'lucknow', 'shimla',
    'roorkee', 'haridwar', 'mussoorie', 'nainital', 'almora',
]

# ── BUILDING CONSTRUCTION KEYWORDS ────────────────────────────────
BUILDING_KEYWORDS = [
    # Core construction
    'construction of building','construction of hospital',
    'construction of hostel','construction of residential',
    'construction of quarter','construction of school',
    'construction of college','construction of complex',
    'construction of block','construction of institute',
    'construction of auditorium','construction of hall',
    'construction of laboratory','construction of workshop',
    'construction of depot','construction of shed',
    'construction of office','construction of warehouse',
    'construction of station building','construction of community',
    'construction of centre','construction of multi',
    'civil construction','building construction',
    'rcc building','rcc construction','rcc work',
    'multi storied','multistory','high rise',
    'prefabricated building','preengineered building',
    'epc for construction','epc contract building',
    'epc works hospital','epc works hostel',
    # Renovation
    'renovation of building','renovation of hospital',
    'renovation of hostel','renovation of office',
    'upgradation of building','rehabilitation of building',
    'reconstruction of building','redevelopment',
    # Housing
    'residential flats','housing complex','ews housing',
    'government housing','staff quarters','type i','type ii',
    'type iii','type iv','type v quarter',
]

# ── RAILWAY CONSTRUCTION KEYWORDS ─────────────────────────────────
RAILWAY_KEYWORDS = [
    'railway station building','station building railway',
    'railway quarter','railway residential','railway colony',
    'railway platform','platform construction',
    'railway tunnel','tunnel construction','tunnelling',
    'track laying','permanent way','p-way construction',
    'rail bridge','railway bridge','viaduct construction',
    'loco shed','coach shed','engine shed','railway shed',
    'railway workshop','railway depot','maintenance depot',
    'railway administrative building','railway office',
    'railway hospital','railway school',
    'scr construction','ecr construction','wcr construction',
    'northern railway construction','eastern railway construction',
    'south central railway','north central railway',
    'engineering procurement construction railway',
    'epc railway','epc rail','civil works railway',
]

# ── EXCLUDE THESE ──────────────────────────────────────────────────
EXCLUDE_KEYWORDS = [
    'supply of material','supply of equipment','supply and delivery',
    'supply of furniture','supply of computer','supply of vehicle',
    'supply of drug','supply of medicine','supply of oxygen',
    'rate contract for supply','procurement of goods',
    'manpower supply','security guard','security service',
    'catering service','housekeeping service','cleaning service',
    'pest control service','horticulture maintenance',
    'software development','it services','computer networking',
    'cctv installation only','printing of','advertisement',
    'vehicle hire','ambulance hire','insurance premium',
    'annual maintenance contract of electrical',
    'annual maintenance contract of lift',
    'operation and maintenance of',
    'hiring of','hire of vehicle',
]

MONTHS = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
          'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ── PAGES TO SCRAPE ────────────────────────────────────────────────
PAGES = [
    # EPC — large value tenders ₹20-500Cr
    {'url': 'https://www.tenderdetail.com/tenders/epc-tenders/1', 'state': '', 'cat': 'infrastructure', 'min': 10, 'max': 500},
    {'url': 'https://www.tenderdetail.com/tenders/epc-tenders/2', 'state': '', 'cat': 'infrastructure', 'min': 10, 'max': 500},
    {'url': 'https://www.tenderdetail.com/tenders/epc-tenders/3', 'state': '', 'cat': 'infrastructure', 'min': 10, 'max': 500},
    # Infrastructure
    {'url': 'https://www.tenderdetail.com/tenders/infrastructure-tenders/1', 'state': '', 'cat': 'infrastructure', 'min': 10, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/infrastructure-tenders/2', 'state': '', 'cat': 'infrastructure', 'min': 10, 'max': 300},
    # Building construction
    {'url': 'https://www.tenderdetail.com/tenders/building-construction-tenders/1', 'state': '', 'cat': 'building', 'min': 10, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/building-construction-tenders/2', 'state': '', 'cat': 'building', 'min': 10, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/building-construction-tenders/3', 'state': '', 'cat': 'building', 'min': 10, 'max': 300},
    # Civil
    {'url': 'https://www.tenderdetail.com/tenders/civil-construction-tenders/1', 'state': '', 'cat': 'building', 'min': 10, 'max': 300},
    # Railway
    {'url': 'https://www.tenderdetail.com/tenders/railways-tenders-today/1', 'state': '', 'cat': 'railway', 'min': 10, 'max': 500},
    # Hospital
    {'url': 'https://www.tenderdetail.com/tenders/hospital-tenders/1', 'state': '', 'cat': 'hospital', 'min': 10, 'max': 300},
    # Housing
    {'url': 'https://www.tenderdetail.com/tenders/housing-tenders/1', 'state': '', 'cat': 'housing', 'min': 10, 'max': 300},
    # Priority states
    {'url': 'https://www.tenderdetail.com/tenders/uttarakhand-tenders/1', 'state': 'Uttarakhand', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/uttarakhand-tenders/2', 'state': 'Uttarakhand', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/uttarakhand-tenders/3', 'state': 'Uttarakhand', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/1', 'state': 'Uttar Pradesh', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/2', 'state': 'Uttar Pradesh', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/1', 'state': 'Himachal Pradesh', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/2', 'state': 'Himachal Pradesh', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/punjab-tenders/1', 'state': 'Punjab', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/punjab-tenders/2', 'state': 'Punjab', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/chandigarh-tenders/1', 'state': 'Chandigarh', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/haryana-tenders/1', 'state': 'Haryana', 'cat': 'building', 'min': 5, 'max': 300},
    {'url': 'https://www.tenderdetail.com/tenders/haryana-tenders/2', 'state': 'Haryana', 'cat': 'building', 'min': 5, 'max': 300},
]

def make_id(title):
    return hashlib.md5(title.lower().encode()).hexdigest()[:20]

def extract_cr(s):
    if not s: return None
    s2 = s.lower().replace(',', '')
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*crore', s2)
    if m: return float(m.group(1))
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lakhs)', s2)
    if m: return float(m.group(1)) / 100
    return None

def is_active(deadline_str):
    if not deadline_str: return True  # no deadline = assume active
    try:
        dl = datetime.strptime(deadline_str, '%Y-%m-%d')
        return dl.date() >= datetime.now().date()
    except: return True

def classify(title, page_cat):
    text = title.lower()
    if any(k in text for k in RAILWAY_KEYWORDS): return 'railway'
    if any(k in text for k in ['hospital','medical','health']): return 'hospital'
    if any(k in text for k in ['housing','residential flat','ews','quarter','colony']): return 'housing'
    return page_cat

def get_seen_ids():
    url = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents/{FB_SEEN_COL}?key={FB_KEY}&pageSize=2000"
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read())
        return set(d['name'].split('/')[-1] for d in data.get('documents', []))
    except: return set()

def mark_seen(tid, title):
    url = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents/{FB_SEEN_COL}/{tid}?key={FB_KEY}"
    payload = json.dumps({"fields": {
        "title": {"stringValue": title[:100]},
        "seenAt": {"timestampValue": datetime.now(timezone.utc).isoformat()},
    }}).encode()
    req = urllib.request.Request(url, data=payload, method='PATCH',
        headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=8, context=ctx)

def write_bot_tender(t):
    doc_id = t['id']
    url = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents/{FB_BOT_COL}/{doc_id}?key={FB_KEY}"
    pri = any(s in (t['name']+t['client']+t['state']).lower() for s in TARGET_STATES)
    payload = json.dumps({"fields": {
        "id": {"stringValue": doc_id},
        "name": {"stringValue": t['name'][:200]},
        "client": {"stringValue": t['client'][:100]},
        "state": {"stringValue": t['state']},
        "value": {"stringValue": t['value']},
        "deadline": {"stringValue": t['deadline']},
        "category": {"stringValue": t['category']},
        "source": {"stringValue": "TenderDetail.com"},
        "link": {"stringValue": t['link']},
        "priorityState": {"booleanValue": pri},
        "discoveredAt": {"timestampValue": datetime.now(timezone.utc).isoformat()},
        "updatedAt": {"timestampValue": datetime.now(timezone.utc).isoformat()},
    }}).encode()
    req = urllib.request.Request(url, data=payload, method='PATCH',
        headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    return resp.status == 200

def scrape_page(page):
    tenders = []
    url = page['url']
    state = page['state']
    cat = page['cat']
    min_cr = page['min']
    max_cr = page['max']

    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-IN,en-GB;q=0.9',
        'Referer': 'https://www.tenderdetail.com/',
        'Cache-Control': 'no-cache',
    })
    resp = urllib.request.urlopen(req, timeout=20, context=ctx)
    html = resp.read().decode('utf-8', errors='ignore')

    rows = re.findall(
        r'<div class="tender_row">([\s\S]*?)(?=<div class="tender_row">|<div[^>]*pagination|$)',
        html
    )

    for block in rows:
        # Title
        tm = re.search(r'class="m-brief"[^>]+title="([^"]+)"', block)
        if not tm: continue
        title = tm.group(1).replace('&amp;', '&').replace('&#039;', "'").strip()
        if len(title) < 12: continue

        text = title.lower()

        # Exclude check
        if any(b in text for b in EXCLUDE_KEYWORDS): continue

        # Must match building OR railway keywords
        is_building = any(k in text for k in BUILDING_KEYWORDS)
        is_railway = any(k in text for k in RAILWAY_KEYWORDS)
        if not is_building and not is_railway: continue

        # Value
        vm = re.search(r'class="tender-value"[\s\S]*?([0-9,]+\.?[0-9]*\s*(?:Crore|Lakhs|Lakh))', block, re.I)
        val_str = vm.group(1).strip() if vm else ''
        val_cr = extract_cr(val_str)

        # Value filter — skip if shown AND out of range
        if val_cr is not None:
            if val_cr < min_cr or val_cr > max_cr:
                continue

        # Deadline
        mo = re.search(r'class="month">([^<]+)<', block)
        dy = re.search(r'class="day">([^<]+)<', block)
        yr = re.search(r'class="year">([^<]+)<', block)
        deadline = ''
        if mo and dy and yr:
            m = MONTHS.get(mo.group(1).strip(), '01')
            deadline = f"{yr.group(1).strip()}-{m}-{dy.group(1).strip().zfill(2)}"

        # Skip expired tenders
        if deadline and not is_active(deadline):
            continue

        # Link
        lm = re.search(r'class="m-brief"[^>]+href="([^"]+)"', block)
        link = lm.group(1) if lm else ''

        # Org
        om = re.search(r'class="workDesc"[\s\S]*?<strong>([\s\S]*?)</strong>', block)
        org = re.sub(r'<[^>]+>', ' ', om.group(1)).strip()[:80] if om else ''
        org = re.sub(r'\s+', ' ', org).strip()

        # Infer state from org if not set
        inferred_state = state
        if not inferred_state:
            for s in ['Uttarakhand','Uttar Pradesh','Himachal Pradesh','Punjab',
                      'Chandigarh','Haryana','Delhi','Rajasthan','Gujarat',
                      'Maharashtra','Karnataka','Tamil Nadu','Andhra Pradesh']:
                if s.lower() in (title + org).lower():
                    inferred_state = s
                    break

        tenders.append({
            'id': make_id(title),
            'name': title,
            'client': org,
            'state': inferred_state,
            'value': f"{val_cr:.2f}" if val_cr else '',
            'deadline': deadline,
            'category': classify(title, cat),
            'link': link,
        })

    return tenders

def main():
    print(f"VKJ Bot starting at {datetime.now().isoformat()}")
    print(f"Scraping {len(PAGES)} pages...")

    # Get already-seen IDs
    seen = get_seen_ids()
    print(f"Already seen: {len(seen)} tenders")

    # Scrape all pages
    all_tenders = []
    for page in PAGES:
        name = page['url'].split('/')[-2]
        try:
            found = scrape_page(page)
            print(f"  {name}: {len(found)} relevant")
            all_tenders.extend(found)
        except Exception as e:
            print(f"  {name}: ERROR — {e}")
        time.sleep(0.4)

    print(f"Total raw: {len(all_tenders)}")

    # Deduplicate by ID (MD5 of title)
    unique = {}
    for t in all_tenders:
        if t['id'] not in unique:
            unique[t['id']] = t
    print(f"Unique: {len(unique)}")

    # Find new ones
    new_tenders = [t for tid, t in unique.items() if tid not in seen]
    print(f"New: {len(new_tenders)}")

    if not new_tenders:
        print("Nothing new. Exiting.")
        return

    # Sort: priority states first, then by deadline
    priority_states_lower = [s.lower() for s in TARGET_STATES]
    def sort_key(t):
        is_pri = any(s in (t['name']+t['state']+t['client']).lower() for s in priority_states_lower)
        dl = t['deadline'] or '9999-12-31'
        return (0 if is_pri else 1, dl)
    new_tenders.sort(key=sort_key)

    # Write to Firebase bot_tenders collection
    written = 0
    for t in new_tenders:
        try:
            ok = write_bot_tender(t)
            if ok:
                mark_seen(t['id'], t['name'])
                written += 1
                print(f"  ✓ {t['name'][:65]} | ₹{t['value'] or '?'} | {t['state'] or 'All India'}")
        except Exception as e:
            print(f"  ✗ {t['name'][:40]}: {e}")
        time.sleep(0.08)

    print(f"\n{'='*50}")
    print(f"DONE: {written} new tenders written to bot_tenders")
    print(f"Open VKJ Portal → 🤖 Bot Tenders tab")

if __name__ == '__main__':
    main()
