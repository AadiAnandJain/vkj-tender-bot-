#!/usr/bin/env python3
"""
VKJ Tender Discovery Bot — Clean Rewrite
Sources: TenderDetail.com (37 pages) + BidAssist via Scrape.do + DFCCIL
Runs: 4x daily via GitHub Actions (7AM, 12PM, 3PM, 6PM IST)
Writes: Firebase bot_tenders collection
"""

import urllib.request, ssl, re, json, time, hashlib, os, urllib.parse
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────
FB_KEY      = "AIzaSyAeAbG_9oNwWNmAzGQR7VgwFiDGNj5-ztg"
FB_PROJECT  = "vkj-tender-tacker"
BOT_COL     = "bot_tenders"
SEEN_COL    = "bot_seen_ids"
SCRAPE_TOKEN = os.environ.get('SCRAPE_DO_TOKEN', 'e9b584c9850043759c69097865fff7747d5424238b5')

PRIORITY_STATES = [
    'uttarakhand','uttar pradesh','himachal pradesh','himachal',
    'punjab','chandigarh','haryana','rajasthan',
    'dehradun','roorkee','haridwar','lucknow','shimla',
    'pathankot','ambala','jaipur','panchkula','mohali',
]

MONTHS = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
          'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ── KEYWORDS ─────────────────────────────────────────────────
BUILD_KW = [
    # New construction
    'construction of building','construction of hospital','construction of hostel',
    'construction of residential','construction of quarter','construction of school',
    'construction of college','construction of complex','construction of block',
    'construction of institute','construction of centre','construction of hall',
    'construction of office','construction of laboratory','construction of workshop',
    'construction of shed','construction of depot','construction of station',
    'construction of staff','construction of faculty','construction of community',
    'construction of medical','construction of health','construction of type',
    'construction of adm block','construction of accn','construction of transit',
    'construction of mess','construction of barracks','construction of armoury',
    'provn of adm','provn of quarters','provn of accn','provn of transit',
    'civil construction','building construction','rcc building','rcc construction',
    'multi storied','multistory','prefabricated building','preengineered',
    'epc contract','epc project','epc works','engineering procurement construction',
    # Renovation / repair
    'renovation of building','renovation of hospital','renovation of hostel',
    'upgradation of building','rehabilitation of building','redevelopment',
    'reconstruction of building','repair of building','retrofitting',
    'repair and maint of bldg','repair/maint of bldg','certain repair',
    'maint of accn','allied bldgs','accn area','repair and maint of accn',
    'repair of accn','maintenance of building','restoration of building',
    # Housing / residential
    'residential flats','housing complex','ews housing','staff quarters',
    'government housing','type i quarter','type ii quarter','type iii quarter',
    # Institutions
    'nbcc','aiims','iit ','nit ','central university','kendriya vidyalaya',
    'navodaya','esic hospital','district hospital','civil hospital',
    'smart city','mes ','cpwd','military engineer','border road',
]

RAILWAY_KW = [
    'railway station building','station building','railway quarter',
    'railway residential','railway colony','railway platform','platform construction',
    'railway tunnel','tunnel construction','tunnelling','tunnel boring',
    'track laying','permanent way','p-way','rail laying',
    'rail over bridge','road over bridge','railway bridge','railway viaduct',
    'loco shed','coach shed','engine shed','railway workshop','railway depot',
    'railway administrative','railway office','railway hospital',
    'station redevelopment','railway station redevelopment',
    'construction of boundary wall','railway compound',
    'railway staff quarters','railway residential complex',
]

BAD_KW = [
    'supply of material','supply of equipment','supply and delivery',
    'supply of drug','supply of medicine','supply of linen',
    'supply of computer','supply of vehicle','supply of furniture',
    'rate contract for supply','procurement of goods',
    'manpower supply','security service','security guard',
    'catering service','housekeeping','cleaning service','pest control',
    'software development','it services','computer networking',
    'printing of','vehicle hire','ambulance hire','insurance premium',
    'annual maintenance contract of electrical','annual maintenance contract of lift',
    'operation and maintenance of','hiring of vehicle',
    'laying of water supply pipeline','laying of sewer line',
    'electrification only','painting work only','whitewashing only',
    'landscaping only','supply and installation of solar',
    'supply and installation of ac','supply and installation of generator',
    'running of canteen',
]

# ── TENDERDETAIL PAGES ────────────────────────────────────────
TD_PAGES = [
    # EPC / Infrastructure
    ('https://www.tenderdetail.com/tenders/epc-tenders/1',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/epc-tenders/2',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/epc-tenders/3',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/epc-tenders/4',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/1',   '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/2',   '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/infrastructure-tenders/3',   '', 'infrastructure', 10, 300),
    # Building
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/1', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/2', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/3', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/building-construction-tenders/4', '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/civil-construction-tenders/1',    '', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/civil-construction-tenders/2',    '', 'building', 5, 300),
    # Hospital / School / Housing
    ('https://www.tenderdetail.com/tenders/hospital-tenders/1',         '', 'hospital',  5, 300),
    ('https://www.tenderdetail.com/tenders/hospital-tenders/2',         '', 'hospital',  5, 300),
    ('https://www.tenderdetail.com/tenders/school-tenders/1',           '', 'building',  5, 300),
    ('https://www.tenderdetail.com/tenders/housing-tenders/1',          '', 'housing',   5, 300),
    # Railway
    ('https://www.tenderdetail.com/tenders/railways-tenders-today/1',   '', 'railway',   10, 500),
    ('https://www.tenderdetail.com/tenders/railways-tenders-today/2',   '', 'railway',   10, 500),
    # Defence / Smart City / Airport
    ('https://www.tenderdetail.com/tenders/defence-tenders/1',          '', 'building',  10, 300),
    ('https://www.tenderdetail.com/tenders/defence-tenders/2',          '', 'building',  10, 300),
    ('https://www.tenderdetail.com/tenders/smart-city-tenders/1',       '', 'infrastructure', 10, 300),
    ('https://www.tenderdetail.com/tenders/airport-tenders/1',          '', 'infrastructure', 10, 300),
    # Priority States
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/1',      'Uttarakhand',      'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/2',      'Uttarakhand',      'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttarakhand-tenders/3',      'Uttarakhand',      'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/1',    'Uttar Pradesh',    'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/uttar-pradesh-tenders/2',    'Uttar Pradesh',    'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/1', 'Himachal Pradesh', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/himachal-pradesh-tenders/2', 'Himachal Pradesh', 'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/punjab-tenders/1',           'Punjab',           'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/punjab-tenders/2',           'Punjab',           'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/chandigarh-tenders/1',       'Chandigarh',       'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/haryana-tenders/1',          'Haryana',          'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/haryana-tenders/2',          'Haryana',          'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/rajasthan-tenders/1',        'Rajasthan',        'building', 5, 300),
    ('https://www.tenderdetail.com/tenders/rajasthan-tenders/2',        'Rajasthan',        'building', 5, 300),
    # New confirmed pages — all verified working with real tenders
    ('https://www.tenderdetail.com/tenders/tunnel-tenders/1',              '', 'railway',       5, 300),
    ('https://www.tenderdetail.com/tenders/airport-tenders/2',             '', 'infrastructure', 5, 300),
    ('https://www.tenderdetail.com/tenders/airport-construction-tenders/1','', 'infrastructure', 5, 300),
    ('https://www.tenderdetail.com/tenders/institutional-tenders/1',       '', 'building',      5, 300),
    ('https://www.tenderdetail.com/tenders/medical-tenders/1',             '', 'hospital',      5, 300),
    ('https://www.tenderdetail.com/tenders/medical-tenders/2',             '', 'hospital',      5, 300),
    ('https://www.tenderdetail.com/tenders/military-tenders/1',            '', 'building',      5, 300),
    ('https://www.tenderdetail.com/tenders/auditorium-tenders/1',          '', 'building',      5, 300),
    ('https://www.tenderdetail.com/tenders/bridge-tenders/1',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/bridge-tenders/2',              '', 'infrastructure', 10, 500),
    ('https://www.tenderdetail.com/tenders/stadium-tenders/1',             '', 'building',      5, 300),
    ('https://www.tenderdetail.com/tenders/sewage-tenders/1',              '', 'infrastructure', 10, 300),
]

# ── HELPERS ───────────────────────────────────────────────────
def make_id(s):
    return hashlib.md5(s.lower().strip().encode()).hexdigest()[:20]

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

def classify(title, default):
    t = title.lower()
    if any(k in t for k in ['tunnel','platform','track laying','permanent way','p-way',
        'loco shed','coach shed','railway station','railway quarter','railway bridge',
        'viaduct','railway workshop','station building']): return 'railway'
    if any(k in t for k in ['hospital','medical college','aiims','health centre','esic']): return 'hospital'
    if any(k in t for k in ['hostel','residential flat','ews','housing complex','colony']): return 'housing'
    if 'epc' in t or 'engineering procurement' in t: return 'infrastructure'
    return default

def infer_state(text):
    text = text.lower()
    state_map = {
        'uttarakhand':'Uttarakhand','uttar pradesh':'Uttar Pradesh','u.p.':'Uttar Pradesh',
        'himachal':'Himachal Pradesh','punjab':'Punjab','chandigarh':'Chandigarh',
        'haryana':'Haryana','rajasthan':'Rajasthan','delhi':'Delhi',
        'jharkhand':'Jharkhand','bihar':'Bihar','gujarat':'Gujarat',
        'maharashtra':'Maharashtra','karnataka':'Karnataka','telangana':'Telangana',
        'andhra':'Andhra Pradesh','kerala':'Kerala','odisha':'Odisha',
        'madhya pradesh':'Madhya Pradesh','chhattisgarh':'Chhattisgarh',
    }
    for k,v in state_map.items():
        if k in text: return v
    return ''

def is_priority(name, state, client):
    return any(s in (name+state+client).lower() for s in PRIORITY_STATES)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── FETCH VIA SCRAPE.DO ───────────────────────────────────────
def fetch(url, render=False):
    encoded = urllib.parse.quote(url, safe='')
    proxy = f"https://api.scrape.do?token={SCRAPE_TOKEN}&url={encoded}"
    if render: proxy += "&render=true"
    req = urllib.request.Request(proxy, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=25, context=ctx)
    return resp.read().decode('utf-8', errors='ignore')

# ── FIREBASE ──────────────────────────────────────────────────
FB = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents"

def fb_get_ids(col):
    url = f"{FB}/{col}?key={FB_KEY}&pageSize=2000"
    req = urllib.request.Request(url, headers={'Accept':'application/json'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    data = json.loads(resp.read())
    return set(d['name'].split('/')[-1] for d in data.get('documents',[]))

def fb_write(col, doc_id, fields):
    url = f"{FB}/{col}/{doc_id}?key={FB_KEY}"
    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(url, data=payload, method='PATCH',
        headers={'Content-Type':'application/json'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    return resp.status == 200

# ── SCRAPER 1: TENDERDETAIL ───────────────────────────────────
def scrape_tenderdetail(url, state, cat, min_cr, max_cr):
    tenders = []
    try:
        html = fetch(url)
        rows = re.findall(
            r'<div class="tender_row">([\s\S]*?)(?=<div class="tender_row">|<div[^>]*pagination|$)',
            html)
        for block in rows:
            tm = re.search(r'class="m-brief"[^>]+title="([^"]+)"', block)
            if not tm: continue
            title = tm.group(1).replace('&amp;','&').replace('&#039;',"'").strip()
            if len(title) < 12: continue
            text = title.lower()
            if any(b in text for b in BAD_KW): continue
            if not any(k in text for k in BUILD_KW+RAILWAY_KW): continue
            vm = re.search(r'class="tender-value"[\s\S]*?([0-9,]+\.?[0-9]*\s*(?:Crore|Lakhs|Lakh))', block, re.I)
            val_str = vm.group(1).strip() if vm else ''
            val_cr = extract_cr(val_str)
            if val_cr is not None and (val_cr < min_cr or val_cr > max_cr): continue
            lm = re.search(r'class="m-brief"[^>]+href="([^"]+)"', block)
            link = lm.group(1) if lm else ''
            om = re.search(r'class="workDesc"[\s\S]*?<strong>([\s\S]*?)</strong>', block)
            org = re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ', om.group(1))).strip()[:100] if om else ''
            mo = re.search(r'class="month">([^<]+)<', block)
            dy = re.search(r'class="day">([^<]+)<', block)
            yr = re.search(r'class="year">([^<]+)<', block)
            deadline = ''
            if mo and dy and yr:
                m = MONTHS.get(mo.group(1).strip(),'01')
                deadline = f"{yr.group(1).strip()}-{m}-{dy.group(1).strip().zfill(2)}"
            if not is_active(deadline): continue
            inferred = state or infer_state(title + ' ' + org)
            tenders.append({
                'id': make_id(title), 'name': title[:200], 'client': org,
                'state': inferred, 'value': f"{val_cr:.2f}" if val_cr else '',
                'deadline': deadline, 'category': classify(title, cat),
                'source': 'TenderDetail.com', 'link': link,
            })
    except Exception as e:
        print(f"    TD error: {e}")
    return tenders

# ── SCRAPER 2: DFCCIL ─────────────────────────────────────────
def scrape_dfccil():
    tenders = []
    try:
        html = fetch('https://dfccil.com/Home/ActiveTender')
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        clean = lambda s: re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ',s).replace('&amp;','&')).strip()
        for row in rows:
            c = clean(row)
            if len(c) < 20: continue
            text = c.lower()
            if any(b in text for b in BAD_KW): continue
            if not any(k in text for k in BUILD_KW+RAILWAY_KW): continue
            lm = re.search(r'href="([^"]+)"', row)
            link = lm.group(1) if lm else 'https://dfccil.com/Home/ActiveTender'
            if not link.startswith('http'): link = 'https://dfccil.com' + link
            dm = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', c)
            deadline = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else ''
            if not is_active(deadline): continue
            tenders.append({
                'id': make_id(c), 'name': c[:200], 'client': 'DFCCIL', 'state': '',
                'value': '', 'deadline': deadline,
                'category': classify(c, 'railway'), 'source': 'DFCCIL',
                'link': link,
            })
    except Exception as e:
        print(f"    DFCCIL error: {e}")
    return tenders

# ── MAIN ──────────────────────────────────────────────────────
# ── SCRAPER: CPPP (eprocure.gov.in) ──────────────────────────
# Returns latest 10 live tenders published on CPPP
# Scraping 4x daily catches ~40 new tenders/day from CPWD, MES, NBCC, IIT, AIIMS etc.
CPPP_URLS = [
    'https://eprocure.gov.in/cppp/latestactivetendersnew/cppp_activity',
]

def scrape_cppp():
    tenders = []
    try:
        url = CPPP_URLS[0]
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-IN,en;q=0.9',
            'Referer': 'https://eprocure.gov.in/cppp/',
        })
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        html = resp.read().decode('utf-8', errors='ignore')

        rows = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', html)
        clean = lambda s: re.sub(r'\\s+', ' ', re.sub(r'<[^>]+>', ' ', s).replace('&amp;','&').replace('&nbsp;',' ')).strip()

        for row in rows[1:]:  # skip header
            c = clean(row)
            if len(c) < 30: continue

            text = c.lower()
            if any(b in text for b in BAD_KW): continue
            if not any(k in text for k in BUILD_KW + RAILWAY_KW): continue

            # Extract dates: published, deadline
            dates = re.findall(r'(\d{2}-\w{3}-\d{4})', c)
            deadline = ''
            if len(dates) >= 2:
                try:
                    from datetime import datetime as _dt
                    dl = _dt.strptime(dates[1], '%d-%b-%Y')
                    deadline = dl.strftime('%Y-%m-%d')
                except: pass
            if not is_active(deadline): continue

            # Extract link
            lm = re.search(r'href="(https://eprocure\.gov\.in[^"]+)"', row)
            link = lm.group(1) if lm else 'https://eprocure.gov.in/cppp/latestactivetendersnew/cppp_activity'

            # Extract org (usually after ref number)
            # Ref pattern: alphanumeric/slash sequences
            ref_m = re.search(r'/([A-Z0-9/-]{8,})/[0-9]+', c)
            ref = ref_m.group(0).strip('/ ') if ref_m else ''

            # Org is usually near the end before '--'
            org = ''
            if '--' in c:
                org = c.split('--')[0].strip().split()[-1] if c.split('--')[0].strip() else ''
            # Try to get full org name
            org_m = re.search(r'(?:CPWD|MES|NBCC|AIIMS|IIT|NIT|PWD|BRO|HUDCO|RVNL|IRCON|DFCCIL|Railway)[^/\d]{0,60}', c, re.I)
            if org_m: org = org_m.group(0).strip()[:80]

            # Infer state from text
            state = infer_state(c)

            tenders.append({
                'id': make_id(c[:100]),
                'name': c[:200],
                'client': org[:100] if org else 'Government of India',
                'state': state,
                'value': '',  # CPPP rarely shows value in listing
                'deadline': deadline,
                'category': classify(c, 'building'),
                'source': 'CPPP',
                'link': link,
            })

    except Exception as e:
        print(f"    CPPP error: {e}")
    return tenders

# ── AI SUMMARY VIA CLAUDE HAIKU ──────────────────────────────────
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')

def generate_ai_summary(tender):
    """Call Claude Haiku to generate GO/NO-GO summary for each tender"""
    if not ANTHROPIC_KEY:
        return None
    try:
        name    = tender.get('name', '')
        client  = tender.get('client', '')
        state   = tender.get('state', '')
        value   = tender.get('value', '')
        cat     = tender.get('category', '')
        source  = tender.get('source', '')

        val_str = f"₹{value} Crore" if value else "Value not disclosed"

        prompt = f"""You are a tender analysis expert for VKJ Projects Pvt. Ltd., a government building construction contractor based in Dehradun with ₹220 Cr annual turnover, CPWD Class I and MES Super Special Class registration, 55+ years experience.

Analyse this tender and return ONLY valid JSON, no explanation:

Tender: {name}
Client: {client}
State: {state}
Value: {val_str}
Category: {cat}

Return this exact JSON:
{{
  "verdict": "GO" or "NO-GO" or "EVALUATE",
  "scope": "One sentence describing what work is involved",
  "pq_likely": "Likely PQ requirements based on client and scale",
  "risk": "Main risk for VKJ in one sentence",
  "why": "One line reason for the verdict"
}}"""

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        result = json.loads(resp.read())
        raw = result["content"][0]["text"].strip()
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"    AI summary error: {e}")
        return None

def main():
    print(f"VKJ Bot starting — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    seen = fb_get_ids(SEEN_COL)
    print(f"Already seen: {len(seen)}")

    all_tenders = []

    # 1. TenderDetail — 37 pages
    print(f"\nScraping TenderDetail ({len(TD_PAGES)} pages)...")
    for url, state, cat, mn, mx in TD_PAGES:
        label = url.split('/')[-2]
        found = scrape_tenderdetail(url, state, cat, mn, mx)
        if found: print(f"  {label}: {len(found)}")
        all_tenders.extend(found)
        time.sleep(0.3)

    # 2. CPPP — Live government tenders from eprocure.gov.in
    print("\n  Scraping CPPP (live government tenders)...")
    try:
        cp = scrape_cppp()
        print(f"  CPPP: {len(cp)} relevant tenders (from CPWD, MES, NBCC, IIT, AIIMS etc.)")
        all_tenders.extend(cp)
    except Exception as e:
        print(f"  CPPP: ERROR — {e}")

    # 3. DFCCIL
    print("\nScraping DFCCIL...")
    df = scrape_dfccil()
    print(f"  DFCCIL: {len(df)} relevant tenders")
    all_tenders.extend(df)

    # Deduplicate
    unique = {}
    for t in all_tenders:
        if t['id'] not in unique:
            unique[t['id']] = t
    print(f"\nTotal unique: {len(unique)}")

    # New only
    new = [t for tid,t in unique.items() if tid not in seen]
    print(f"New this run: {len(new)}")
    if not new:
        print("Nothing new. Done.")
        return

    # Sort — priority states first
    new.sort(key=lambda t: (
        0 if is_priority(t['name'], t['state'], t['client']) else 1,
        t['deadline'] or '9999-12-31'
    ))

    # Write to Firebase
    written = 0
    for t in new:
        pri = is_priority(t['name'], t['state'], t['client'])
        try:
            ok = fb_write(BOT_COL, t['id'], {
                'id':            {'stringValue': t['id']},
                'name':          {'stringValue': t['name']},
                'client':        {'stringValue': t['client']},
                'state':         {'stringValue': t['state']},
                'value':         {'stringValue': t['value']},
                'deadline':      {'stringValue': t['deadline']},
                'category':      {'stringValue': t['category']},
                'source':        {'stringValue': t['source']},
                'link':          {'stringValue': t['link']},
                'priorityState': {'booleanValue': pri},
                'discoveredAt':  {'timestampValue': now_iso()},
                'updatedAt':     {'timestampValue': now_iso()},
            })
            if ok:
                fb_write(SEEN_COL, t['id'], {
                    'title':  {'stringValue': t['name'][:100]},
                    'seenAt': {'timestampValue': now_iso()},
                })
                written += 1
                src = t['source']
                print(f"  ✓ [{src}] {t['name'][:55]} | ₹{t['value'] or '?'} | {t['state'] or 'All India'}")
        except Exception as e:
            print(f"  ✗ {t['name'][:40]}: {e}")
        time.sleep(0.08)

    print(f"\n{'='*55}")
    print(f"Done: {written} new tenders written")
    print(f"Open portal → 🤖 Bot Tenders tab")

if __name__ == '__main__':
    main()
