import requests
import datetime
import time
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


FRONTEND_TOKEN = requests.get("https://bbradar.io/api/frontend-token").json()["frontend_token"]
CSRF_TOKEN = requests.post("https://bbradar.io/api/csrf-token", json={"frontend_token": FRONTEND_TOKEN}).json()["csrf_token"]

API_BASE = "https://bbradar.io/api"
OUTPUT_FILE = "docs/feed.atom"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://bbradar.io/',
    'Content-Type': 'application/json',
    'X-CSRF-Token': CSRF_TOKEN,
    'Connection': 'keep-alive',
    'Priority': 'u=4'
}

def fetch_json(url, params=None):
    """Simple fetch with a small sleep to be polite."""
    time.sleep(0.2) 
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[!] Error fetching {url}: {e}")
        return None

def parse_date(date_str):
    if not date_str:
        return datetime.datetime.now(datetime.timezone.utc)
    
    formats = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return datetime.datetime.now(datetime.timezone.utc)

def build_content_html(program, targets):
    html = f"<div><img src='{program.get('profile_picture')}' width='50' style='float:left; margin-right:10px;' />"
    html += f"<b>Platform:</b> {program.get('platform')}<br/>"
    html += f"<b>Bounty:</b> ${program.get('bounty_min', 0):,} - ${program.get('bounty_max', 'Infinite')}<br/></div><br clear='all'/>"

    if targets:
        html += "<h3>Scope Targets</h3><ul>"
        for t in targets:
            html += f"<li>[{t.get('target_type')}] {t.get('identifier')}</li>"
        html += "</ul>"
    return html

def main():
    print("[-] Fetching program list...")
    programs = fetch_json(f"{API_BASE}/programs")
    if not programs: return

    programs = list(reversed(sorted(programs, key=lambda x: x["date_launched"])))[:100]

    now = datetime.datetime.now(datetime.timezone.utc)
    valid_programs = []
    
    for p in programs:
        p_date = parse_date(p.get('date_launched'))
        if p_date <= now:
            p['_date'] = p_date
            valid_programs.append(p)
            
    valid_programs.sort(key=lambda x: x['_date'].timestamp(), reverse=True)

    feed = Element('feed', xmlns="http://www.w3.org/2005/Atom")
    SubElement(feed, 'title').text = "BBRadar Feed"
    SubElement(feed, 'updated').text = now.isoformat()

    print(f"[-] Processing {len(valid_programs)} programs serially...")

    for i, prog in enumerate(valid_programs):
        print(f"[{i+1}/{len(valid_programs)}] {prog.get('name')}")
        
        pid = f"{prog['platform']}:{prog['handle']}"
        data = fetch_json(f"{API_BASE}/targets", params={'program_id': pid})
        targets = data.get('targets', []) if data else []

        entry = SubElement(feed, 'entry')
        SubElement(entry, 'title').text = f"[{prog.get('platform')}] {prog.get('name')}"
        
        link = prog.get('link') or f"https://bbradar.io/program/{pid}"
        SubElement(entry, 'link', href=link)
        SubElement(entry, 'id').text = link
        SubElement(entry, 'updated').text = prog['_date'].isoformat()
        
        content = SubElement(entry, 'content', type="html")
        content.text = build_content_html(prog, targets)

    xml_str = minidom.parseString(tostring(feed)).toprettyxml(indent="  ")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print("[-] Done.")

if __name__ == "__main__":
    main()
