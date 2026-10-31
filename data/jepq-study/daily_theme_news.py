"""Theme-tagged Google News around each daily pivot (window day-2..day+2)."""
import json, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date, timedelta
OUT = sys.argv[1]
piv = json.load(open(f"{OUT}/daily_pivots.json"))
EN = "hl=en-US&gl=US&ceid=US:en"; KO = "hl=ko&gl=KR&ceid=KR:ko"
THEMES = {  # query, title regex used to count on-theme headlines
 "war":       ("stocks (war OR missile OR invasion OR Israel OR Iran OR Ukraine OR Russia OR Hamas OR airstrike)",
               r"\b(war|missile|invasion|israel|iran|ukrain|russia|hamas|gaza|strike|attack|geopolit|middle east|conflict)", EN),
 "fed_rates": ("stocks (Fed OR Powell OR FOMC OR \"rate hike\" OR \"rate cut\")",
               r"\b(fed|powell|fomc|rate hike|rate cut|rate-cut|rate-hike|interest rate|basis point|hawkish|dovish)", EN),
 "treasury":  ("stocks (\"Treasury yields\" OR \"bond yields\" OR \"10-year yield\" OR \"bond market\")",
               r"(treasur|bond|yield)", EN),
 "trump":     ("stocks (Trump OR tariff OR tariffs OR \"White House\")",
               r"\b(trump|tariff|white house|trade war|executive order)", EN),
 "inflation_jobs": ("stocks (CPI OR inflation OR \"jobs report\" OR payrolls OR PCE)",
               r"\b(cpi|inflation|jobs report|payroll|pce|unemployment|jobless|labor market)", EN),
 "ko_macro":  ("뉴욕증시 (금리 OR 국채 OR 전쟁 OR 트럼프 OR 관세 OR 연준 OR 인플레이션)",
               r"(금리|국채|전쟁|트럼프|관세|연준|파월|인플레|물가|이란|이스라엘|우크라|러시아|중동|고용)", KO),
}
def fetch(q, loc, a, b):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{q} after:{a} before:{b}')}&{loc}"
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
    return [{"title": it.findtext("title") or "", "source": it.findtext("source"), "pub": it.findtext("pubDate"),
             "link": it.findtext("link")} for it in ET.fromstring(xml).iter("item")]
out = []
for p in piv:
    d = date.fromisoformat(p["day"]); a, b = d - timedelta(days=2), d + timedelta(days=3)
    themes = {}
    for name, (q, rx, loc) in THEMES.items():
        try:
            items = fetch(q, loc, a, b)
        except Exception as e:
            themes[name] = {"error": str(e)[:100], "n": 0, "on_theme": 0, "items": []}; continue
        hit = [x for x in items if re.search(rx, x["title"], re.I)]
        themes[name] = {"n": len(items), "on_theme": len(hit), "items": hit[:6]}
        time.sleep(0.8)
    out.append({**p, "window": f"{a}..{b - timedelta(days=1)}", "themes": themes})
    print(p["kind"], p["day"], {k: v["on_theme"] for k, v in themes.items()}, flush=True)
json.dump(out, open(f"{OUT}/daily_theme_news.json", "w"), indent=1, ensure_ascii=False)
print("done")
