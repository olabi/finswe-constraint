"""Add a PMI theme (EN + KO news) and ISM release-date proximity to each daily pivot."""
import json, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date, timedelta
import pandas as pd
OUT = sys.argv[1]
d = json.load(open(f"{OUT}/daily_theme_news.json"))
EN = "hl=en-US&gl=US&ceid=US:en"; KO = "hl=ko&gl=KR&ceid=KR:ko"
Q = {
 "pmi":    ("stocks (PMI OR ISM OR \"purchasing managers\" OR \"manufacturing index\" OR \"services index\")",
            r"\b(pmi|ism|purchasing manager|manufacturing (index|activity|survey|sector)|services (index|activity|sector)|factory activity)", EN),
 "ko_pmi": ("뉴욕증시 (PMI OR 구매관리자지수 OR ISM OR 제조업지수 OR 서비스업지수)",
            r"(PMI|ISM|구매관리자|제조업\s*지수|서비스업\s*지수|제조업\s*경기|서비스업\s*경기)", KO),
}
bd = pd.bdate_range("2022-04-01", "2026-12-31")
def nth_bday(y, m, n):
    days = [x for x in bd if x.year == y and x.month == m]
    return days[n - 1].date()
def fetch(q, loc, a, b):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{q} after:{a} before:{b}')}&{loc}"
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
    return [{"title": it.findtext("title") or "", "source": it.findtext("source"), "pub": it.findtext("pubDate"),
             "link": it.findtext("link")} for it in ET.fromstring(xml).iter("item")]
for p in d:
    day = date.fromisoformat(p["day"]); a, b = day - timedelta(days=2), day + timedelta(days=3)
    for name, (q, rx, loc) in Q.items():
        try:
            items = fetch(q, loc, a, b)
            hit = [x for x in items if re.search(rx, x["title"], re.I)]
            p["themes"][name] = {"n": len(items), "on_theme": len(hit), "items": hit[:6]}
        except Exception as e:
            p["themes"][name] = {"error": str(e)[:100], "n": 0, "on_theme": 0, "items": []}
        time.sleep(0.8)
    # ISM release proximity: manufacturing = 1st business day, services = 3rd business day
    rel = []
    for mo in (day.replace(day=1) - timedelta(days=1), day, (day.replace(day=28) + timedelta(days=4))):
        rel += [("ISM-mfg", nth_bday(mo.year, mo.month, 1)), ("ISM-svc", nth_bday(mo.year, mo.month, 3))]
    near = [(k, r.isoformat(), int(len(pd.bdate_range(min(r, day), max(r, day))) - 1)) for k, r in rel
            if abs(len(pd.bdate_range(min(r, day), max(r, day))) - 1) <= 2]
    p["pmi_release_near"] = near
    print(p["kind"], p["day"], "pmi", p["themes"]["pmi"]["on_theme"], "ko_pmi", p["themes"]["ko_pmi"]["on_theme"],
          "| ISM within ±2bd:", [f"{k} {r} ({n}bd)" for k, r, n in near], flush=True)
json.dump(d, open(f"{OUT}/daily_theme_news.json", "w"), indent=1, ensure_ascii=False)
print("done")
