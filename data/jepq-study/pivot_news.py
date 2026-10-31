"""Google News RSS around each weekly pivot (date-bounded queries)."""
import json, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date, timedelta
OUT = sys.argv[1]
piv = json.load(open(f"{OUT}/weekly_pivots.json"))
QUERIES = [("en", "Nasdaq stocks", "hl=en-US&gl=US&ceid=US:en"), ("ko", "나스닥", "hl=ko&gl=KR&ceid=KR:ko")]
res = []
for p in piv:
    d = date.fromisoformat(p["day"])
    after, before = d - timedelta(days=3), d + timedelta(days=4)
    items = []
    for lang, q, loc in QUERIES:
        qs = urllib.parse.quote(f"{q} after:{after} before:{before}")
        url = f"https://news.google.com/rss/search?q={qs}&{loc}"
        try:
            xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
            for it in ET.fromstring(xml).iter("item"):
                items.append({"lang": lang, "title": it.findtext("title"), "source": it.findtext("source"),
                              "pub": it.findtext("pubDate"), "link": it.findtext("link")})
        except Exception as e:
            items.append({"lang": lang, "error": str(e)[:120]})
        time.sleep(1.0)
    res.append({**p, "window": f"{after}..{before}", "news": items})
json.dump(res, open(f"{OUT}/pivot_news.json", "w"), indent=1, ensure_ascii=False)
for r in res:
    en = [n for n in r["news"] if n.get("lang") == "en" and n.get("title")]
    ko = [n for n in r["news"] if n.get("lang") == "ko" and n.get("title")]
    print(f"\n### {r['kind'].upper()} {r['day']} (window {r['window']}) en={len(en)} ko={len(ko)}")
    for n in en[:9]:
        print(f"  [en] {n['pub'][5:16]} | {n['source']} | {n['title'][:150]}")
    for n in ko[:7]:
        print(f"  [ko] {n['pub'][5:16]} | {n['source']} | {n['title'][:120]}")
