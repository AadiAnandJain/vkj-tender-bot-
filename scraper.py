#!/usr/bin/env python3
"""
VKJ Tender Discovery Bot v2
Sources: tenderdetail.com (multi-page) + DFCCIL direct
States: UK, UP, HP, Punjab, Chandigarh, Haryana, Rajasthan + All India EPC/Infra
Departments: NBCC, CPWD, PWD, Railways/DFCCIL, AIIMS, IIT/NIT, Smart City, Defence/MES
Work Types: New building, Hospital, Hostel, Railway, EPC, Renovation
Value: 10-300 Cr (building), 10-500 Cr (railway/DFCCIL)
"""

import urllib.request, json, ssl, re, json, time, hashlib
from datetime import datetime, timezone

FB_KEY     = "AIzaSyAeAbG_9oNwWNmAzGQR7VgwFiDGNj5-ztg"
FB_PROJECT = "vkj-tender-tacker"
BOT_COL    = "bot_tenders"
SEEN_COL   = "bot_seen_ids"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

MONTHS = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
          'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}

TARGET_STATES = [
    'uttarakhand','uttar pradesh','himachal pradesh','himachal',
    'punjab','chandigarh','haryana','rajasthan',
    'dehradun','lucknow','shimla','roorkee','haridwar','nainital',
    'pathankot','ambala','jaipur','jodhpur','panchkula','mohali',
    'uk','up','hp',
]

# ── KEYWORDS ─────────────────────────────────────────────────────
BUILDING_KW = [
    'construction of building','construction of hospital','construction of hostel',
    'construction of residential','construction of quarter','construction of school',
    'construction of college','construction of complex','construction of block',
    'construction of institute','construction of centre','construction of hall',
    'construction of office','construction of laboratory','construction of workshop',
    'construction of shed','construction of depot','construction of station',
    'construction of staff','construction of type','construction of faculty',
    'construction of community','construction of medical','construction of health',
    'civil construction','building construction','rcc building','rcc construction',
    'multi storied','multistory','prefabricated building','preengineered building',
    'epc contract','epc project','epc works','engineering procurement construction',
    'renovation of building','renovation of hospital','renovation of hostel',
    'upgradation of building','rehabilitation of building','redevelopment',
    'reconstruction of building','repair of building','strengthening of building',
    'residential flats','housing complex','ews housing','staff quarters',
    'government housing','type i quarter','type ii quarter','type iii quarter',
    'nbcc','aiims construction','iit construction','nit construction',
    'smart city construction','mes construction','bro construction',
    'kendriya vidyalaya building','navodaya building','esic hospital',
    'district hospital construction','civil hospital construction',
]

RAILWAY_KW = [
    'railway station building','station building','railway quarter',
    'railway residential','railway colony','railway platform','platform construction',
    'railway tunnel','tunnel construction','tunnelling','tunnel boring',
    'track laying','permanent way','p-way','rail laying','ballasting',
    'rail over bridge','road over bridge','railway bridge','railway viaduct',
    'viaduct construction','loco shed','coach shed','engine shed',
    'railway workshop','railway depot','maintenance depot',
    'railway administrative','railway office','railway hospital',
    'construction of boundary wall','maintenance of building',
    'construction of rail flyover','construction of foot over bridge',
    'railway station redevelopment','station redevelopment',
    'construction of staff quarters railway','construction of compound',
]

BAD_KW = [
    'supply of material','supply of equipment','supply and delivery',
    'supply of drug','supply of medicine','supply of linen','supply of uniform',
    'supply of computer','supply of vehicle','supply of furniture',
    'rate contract for supply','procurement of goods','procurement of material',
    'manpower supply','security guard service','security service',
    'catering service','housekeeping','cleaning service','pest control',
    'software development','it services','computer networking','cctv supply',
    'printing of','vehicle hire','ambulance hire','insurance premium',
    'annual maintenance contract of electrical','annual maintenance contract of lift',
    'operation and maintenance of','hiring of vehicle',
    'laying of water supply pipeline','laying of sewer line',
    'electrification only','painting work only','whitewashing only',
    'landscaping only','horticulture maintenance','running of canteen',
    'supply and installation of solar','supply and installation of ac',
    'supply and installation of generator',
]

# ── TENDERDETAIL PAGES ───────────────────────────────────────────
TD_PAGES = [
    # Large value tenders
    ('https://www.tenderdetail.com/tenders/epc-tenders/1',             '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/epc-tenders/2',             '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/epc-tenders/3',             '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/1',  '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/2',  '', 'infrastructure', 10, 300),
    # Building
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/1', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/2', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/3', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/civil-construction-tenders/1',    '', 'building', 5, 300),
    # Hospital
    ('https://www.tenderdetail.com/tenders/hospital-tenders/1',        '', 'hospital', 5, 300),
    # Railway
    ('https://www.tenderdetail.com/tenders/railways-tenders-today/1',  '', 'railway', 10, 500),
    # Defence
    ('https://www.tenderdetail.com/tenders/defence-tenders/1',         '', 'building', 10, 300),
    # Smart city
    ('https://www.tenderdetail.com/tenders/smart-city-tenders/1',      '', 'infrastructure', 10, 300),
    # Housing
    ('https://www.tenderdetail.com/tenders/housing-tenders/1',         '', 'housing', 5, 300),
    # Priority states
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/1',     'Uttarakhand',     'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/2',     'Uttarakhand',     'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/3',     'Uttarakhand',     'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/1',   'Uttar Pradesh',   'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/2',   'Uttar Pradesh',   'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/1','Himachal Pradesh', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/2','Himachal Pradesh', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/punjab-tenders/1',          'Punjab',          'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/punjab-tenders/2',          'Punjab',          'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/chandigarh-tenders/1',      'Chandigarh',      'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/haryana-tenders/1',         'Haryana',         'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/haryana-tenders/2',         'Haryana',         'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/rajasthan-tenders/1',       'Rajasthan',       'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/rajasthan-tenders/2',       'Rajasthan',       'building', 5, 300),
    # New confirmed pages — large tenders found
    ('https://www.tenderdetail.com/tenders/hospital-tenders/2',         '', 'hospital',      5, 300),
    ('https://www.tenderdetail.com/tenders/airport-tenders/1',          '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/defence-tenders/2',          '', 'building',      10, 300),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/3',   '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/epc-tenders/4',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/school-tenders/1',           '', 'building',      5,  300),
    ('https://www.tenderdetail.com/tenders/civil-construction-tenders/2', '', 'building',    5,  300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/4', '', 'building', 5,  300),
]

# ── HELPERS ───────────────────────────────────────────────────────
def make_id(title):
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:20]

def extract_cr(s):
    if not s: return None
    s = s.lower().replace(',','')
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*crore', s)
    if m: return float(m.group(1))
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lakhs)', s)
    if m: return float(m.group(1))/100
    return None

def is_active(dl):
    if not dl: return True
    try: return datetime.strptime(dl,'%Y-%m-%d').date() >= datetime.now().date()
    except: return True

def classify(title, page_cat):
    t = title.lower()
    if any(k in t for k in ['tunnel','tunnelling','platform','track laying','permanent way','p-way','loco shed','coach shed','railway station','station building','railway quarter','railway bridge','viaduct','railway workshop']): return 'railway'
    if any(k in t for k in ['hospital','medical college','aiims','health centre','dispensary','esic']): return 'hospital'
    if any(k in t for k in ['hostel','residential flat','ews','quarter','housing complex','colony','flats']): return 'housing'
    if 'epc' in t or 'engineering procurement' in t: return 'infrastructure'
    return page_cat

def infer_state(title, org):
    text = (title + ' ' + org).lower()
    state_map = {
        'uttarakhand':'Uttarakhand','uttar pradesh':'Uttar Pradesh','u.p.':'Uttar Pradesh',
        'himachal':'Himachal Pradesh','punjab':'Punjab','chandigarh':'Chandigarh',
        'haryana':'Haryana','rajasthan':'Rajasthan','delhi':'Delhi',
        'jharkhand':'Jharkhand','bihar':'Bihar','gujarat':'Gujarat',
        'maharashtra':'Maharashtra','karnataka':'Karnataka','telangana':'Telangana',
        'andhra':'Andhra Pradesh','kerala':'Kerala','odisha':'Odisha',
        'west bengal':'West Bengal','madhya pradesh':'Madhya Pradesh',
        'chhattisgarh':'Chhattisgarh','assam':'Assam','jammu':'Jammu & Kashmir',
    }
    for k,v in state_map.items():
        if k in text: return v
    return ''

def fb_get(col, page_size=2000):
    url = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents/{col}?key={FB_KEY}&pageSize={page_size}"
    req = urllib.request.Request(url, headers={'Accept':'application/json'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    data = json.loads(resp.read())
    return set(d['name'].split('/')[-1] for d in data.get('documents',[]))

def fb_patch(col, doc_id, fields):
    url = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents/{col}/{doc_id}?key={FB_KEY}"
    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(url, data=payload, method='PATCH', headers={'Content-Type':'application/json'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    return resp.status == 200

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── SCRAPERS ──────────────────────────────────────────────────────
import os
SCRAPE_DO_TOKEN = os.environ.get('SCRAPE_DO_TOKEN', '')

def scrape_url(target_url, render=False):
    """Fetch URL via Scrape.do proxy to bypass rate limits"""
    import urllib.parse as urlparse
    encoded = urlparse.quote(target_url, safe='')
    proxy_url = f"https://api.scrape.do?token={SCRAPE_DO_TOKEN}&url={encoded}"
    if render:
        proxy_url += "&render=true"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=25, context=ctx)
    return resp.read().decode('utf-8', errors='ignore')

def scrape_tenderdetail(url, state, cat, min_cr, max_cr):
    tenders = []
    html = scrape_url(url)

    rows = re.findall(
        r'<div class="tender_row">([\s\S]*?)(?=<div class="tender_row">|<div[^>]*pagination|$)',
        html
    )
    for block in rows:
        tm = re.search(r'class="m-brief"[^>]+title="([^"]+)"', block)
        if not tm: continue
        title = tm.group(1).replace('&amp;','&').replace('&#039;',"'").strip()
        if len(title) < 12: continue

        text = title.lower()
        if any(b in text for b in BAD_KW): continue
        is_bld = any(k in text for k in BUILDING_KW)
        is_rly = any(k in text for k in RAILWAY_KW)
        if not is_bld and not is_rly: continue

        vm = re.search(r'class="tender-value"[\s\S]*?([0-9,]+\.?[0-9]*\s*(?:Crore|Lakhs|Lakh))', block, re.I)
        val_str = vm.group(1).strip() if vm else ''
        val_cr = extract_cr(val_str)
        if val_cr is not None and (val_cr < min_cr or val_cr > max_cr): continue

        lm = re.search(r'class="m-brief"[^>]+href="([^"]+)"', block)
        link = lm.group(1) if lm else ''

        om = re.search(r'class="workDesc"[\s\S]*?<strong>([\s\S]*?)</strong>', block)
        org = re.sub(r'<[^>]+>',' ', om.group(1)).strip()[:100] if om else ''
        org = re.sub(r'\s+',' ', org).strip()

        mo = re.search(r'class="month">([^<]+)<', block)
        dy = re.search(r'class="day">([^<]+)<', block)
        yr = re.search(r'class="year">([^<]+)<', block)
        deadline = ''
        if mo and dy and yr:
            m = MONTHS.get(mo.group(1).strip(),'01')
            deadline = f"{yr.group(1).strip()}-{m}-{dy.group(1).strip().zfill(2)}"
        if not is_active(deadline): continue

        inferred_state = state or infer_state(title, org)

        tenders.append({
            'id': make_id(title),
            'name': title[:200], 'client': org, 'state': inferred_state,
            'value': f"{val_cr:.2f}" if val_cr else '',
            'deadline': deadline, 'category': classify(title, cat),
            'source': 'TenderDetail.com', 'link': link,
        })
    return tenders

def scrape_dfccil():
    tenders = []
    req = urllib.request.Request('https://dfccil.com/Home/ActiveTender', headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    resp = urllib.request.urlopen(req, timeout=20, context=ctx)
    html = resp.read().decode('utf-8', errors='ignore')
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        clean = re.sub('<[^>]+>',' ', row)
        clean = re.sub(r'\s+',' ', clean).strip()
        if len(clean) < 20: continue
        text = clean.lower()
        if any(b in text for b in BAD_KW): continue
        is_bld = any(k in text for k in BUILDING_KW)
        is_rly = any(k in text for k in RAILWAY_KW)
        if not is_bld and not is_rly: continue
        lm = re.search(r'href="([^"]+)"', row)
        link = lm.group(1) if lm else 'https://dfccil.com/Home/ActiveTender'
        if not link.startswith('http'): link = 'https://dfccil.com' + link
        dm = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', clean)
        deadline = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else ''
        if deadline and not is_active(deadline): continue
        title = clean[:200]
        tenders.append({
            'id': make_id(title),
            'name': title, 'client': 'DFCCIL', 'state': '',
            'value': '', 'deadline': deadline,
            'category': classify(title,'railway'),
            'source': 'DFCCIL', 'link': link,
        })
    return tenders

# ── MAIN ──────────────────────────────────────────────────────────
# ── BIDASSIST VIA SCRAPE.DO ───────────────────────────────────
BIDASSIST_STATES = [
    ('Uttarakhand',     'Uttarakhand'),
    ('Uttar+Pradesh',   'Uttar Pradesh'),
    ('Himachal+Pradesh','Himachal Pradesh'),
    ('Punjab',          'Punjab'),
    ('Chandigarh',      'Chandigarh'),
    ('Haryana',         'Haryana'),
    ('Rajasthan',       'Rajasthan'),
    ('Delhi',           'Delhi'),
]

def scrape_bidassist(state_param, state_name):
    """Scrape BidAssist via Scrape.do JS rendering — gets real CPPP tender data"""
    tenders = []
    try:
        url = f"https://bidassist.com/global-tenders/active?category=Works&state={state_param}"
        html = scrape_url(url, render=True)

        # Find content array in rendered JSON
        content_m = re.search(r'"content":\[', html)
        if not content_m:
            return tenders
        arr_start = html.find('[', content_m.start())
        depth = 0; i = arr_start; arr_end = len(html)
        while i < len(html):
            if html[i] == '[': depth += 1
            elif html[i] == ']':
                depth -= 1
                if depth == 0: arr_end = i+1; break
            i += 1

        tender_list = json.loads(html[arr_start:arr_end])

        for t in tender_list:
            title = (t.get('tenderDescription') or '').strip()
            if not title or len(title) < 15: continue

            text = title.lower()
            if any(b in text for b in BAD_KW): continue
            is_bld = any(k in text for k in BUILDING_KW)
            is_rly = any(k in text for k in RAILWAY_KW)
            if not is_bld and not is_rly: continue

            # Value in paise/rupees → convert to crore
            raw_val = float(t.get('value', 0) or 0)
            val_cr = None
            if raw_val > 10000000:   val_cr = round(raw_val / 10000000, 2)
            elif raw_val > 100000:   val_cr = round(raw_val / 100000, 2)
            elif raw_val > 0:        val_cr = round(raw_val, 2)

            if val_cr is not None and (val_cr < 5 or val_cr > 500):
                continue

            # Deadline from Unix timestamp ms
            dl_ts = t.get('bidDeadLine') or t.get('closingDate')
            deadline = ''
            if dl_ts:
                try:
                    deadline = datetime.fromtimestamp(int(dl_ts)/1000).strftime('%Y-%m-%d')
                except: pass
            if not is_active(deadline): continue

            org = (t.get('purchaserName') or t.get('displayPurchaserName') or '').strip()[:100]
            link = f"https://bidassist.com/tenders/{t.get('tenderId','')}"
            tid = make_id(title)

            tenders.append({
                'id': tid,
                'name': title[:200],
                'client': org,
                'state': state_name,
                'value': str(val_cr) if val_cr else '',
                'deadline': deadline,
                'category': classify(title, 'building'),
                'source': 'BidAssist',
                'link': link,
            })

    except Exception as e:
        print(f"  BidAssist {state_name}: {e}")
    return tenders

def main():
    print(f"VKJ Bot v2 starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get seen IDs
    seen = fb_get(SEEN_COL)
    print(f"Already seen: {len(seen)}")

    all_tenders = []

    # Scrape tenderdetail pages
    for url, state, cat, mn, mx in TD_PAGES:
        label = url.split('/')[-2]
        try:
            found = scrape_tenderdetail(url, state, cat, mn, mx)
            print(f"  {label}: {len(found)} relevant")
            all_tenders.extend(found)
        except Exception as e:
            print(f"  {label}: ERROR — {e}")
        time.sleep(0.4)

    # Scrape BidAssist via Scrape.do (gets CPPP/govt data through JS rendering)
    print("  Scraping BidAssist (priority states)...")
    for state_param, state_name in BIDASSIST_STATES:
        try:
            ba_tenders = scrape_bidassist(state_param, state_name)
            print(f"    {state_name}: {len(ba_tenders)} relevant")
            all_tenders.extend(ba_tenders)
        except Exception as e:
            print(f"    BidAssist {state_name}: ERROR — {e}")
        time.sleep(1.0)  # Respect Scrape.do rate limits

    # Scrape DFCCIL
    try:
        dfccil = scrape_dfccil()
        print(f"  DFCCIL: {len(dfccil)} relevant")
        all_tenders.extend(dfccil)
    except Exception as e:
        print(f"  DFCCIL: ERROR — {e}")

    print(f"Total raw: {len(all_tenders)}")

    # Deduplicate
    unique = {}
    for t in all_tenders:
        if t['id'] not in unique:
            unique[t['id']] = t
    print(f"Unique: {len(unique)}")

    # New only
    new = [t for tid,t in unique.items() if tid not in seen]
    print(f"New: {len(new)}")
    if not new:
        print("Nothing new. Done.")
        return

    # Sort — priority states first, then deadline
    pri = set(TARGET_STATES)
    def sort_key(t):
        is_pri = any(s in (t['name']+t['state']+t['client']).lower() for s in pri)
        return (0 if is_pri else 1, t['deadline'] or '9999-12-31')
    new.sort(key=sort_key)

    # Write to Firebase
    written = 0
    for t in new:
        is_pri = any(s in (t['name']+t['state']+t['client']).lower() for s in pri)
        try:
            ok = fb_patch(BOT_COL, t['id'], {
                'id':           {'stringValue': t['id']},
                'name':         {'stringValue': t['name']},
                'client':       {'stringValue': t['client']},
                'state':        {'stringValue': t['state']},
                'value':        {'stringValue': t['value']},
                'deadline':     {'stringValue': t['deadline']},
                'category':     {'stringValue': t['category']},
                'source':       {'stringValue': t['source']},
                'link':         {'stringValue': t['link']},
                'priorityState':{'booleanValue': is_pri},
                'discoveredAt': {'timestampValue': now_iso()},
                'updatedAt':    {'timestampValue': now_iso()},
            })
            if ok:
                fb_patch(SEEN_COL, t['id'], {
                    'title':  {'stringValue': t['name'][:100]},
                    'seenAt': {'timestampValue': now_iso()},
                })
                written += 1
                print(f"  ✓ {t['name'][:65]} | ₹{t['value'] or '?'} | {t['state'] or 'All India'}")
        except Exception as e:
            print(f"  ✗ {t['name'][:40]}: {e}")
        time.sleep(0.08)

    print(f"\n{'='*55}")
    print(f"Done: {written} new tenders written to bot_tenders")
    print(f"Open VKJ Portal → 🤖 Bot Tenders tab")

if __name__ == '__main__':
    main()
