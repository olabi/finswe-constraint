"""Point-in-time news: items published after `now` are never returned."""
import sys; sys.path.insert(0, sys.argv[1])
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from kit import Check, Violation, run_checks
from ai_trader.news import parse_headlines

T = datetime(2025, 11, 20, 21, 30, tzinfo=timezone.utc)


def rss(items):
    return "<rss><channel>" + "".join(
        f"<item><title>{t}</title><pubDate>{format_datetime(d)}</pubDate></item>" for t, d in items) + "</channel></rss>"


def drops_future():
    out = " | ".join(parse_headlines(rss([("earnings beat", T - timedelta(minutes=40)),
                                           ("guidance cut", T + timedelta(hours=9)),
                                           ("analyst note", T - timedelta(days=2))]), n=10, now=T))
    if "guidance cut" in out:
        raise Violation(f"headline published 9h after `now` was returned: {out}")
    if "earnings beat" not in out:
        raise Violation(f"a past headline went missing: {out}")


def boundary_kept():
    out = " | ".join(parse_headlines(rss([("exactly now", T), ("one second later", T + timedelta(seconds=1))]),
                                     n=10, now=T))
    if "exactly now" not in out or "one second later" in out:
        raise Violation(f"boundary handling wrong (publish == now kept, now+1s dropped): {out}")


def offset_compared_as_instants():
    # Same instants as T ∓ 1 min, written in +09:00 and −05:00. A comparison on wall-clock
    # text or naive times keeps or drops the wrong one on at least one side.
    seoul, ny = timezone(timedelta(hours=9)), timezone(timedelta(hours=-5))
    items = [("kst before", (T - timedelta(minutes=1)).astimezone(seoul)),
             ("kst after", (T + timedelta(minutes=1)).astimezone(seoul)),
             ("est before", (T - timedelta(minutes=1)).astimezone(ny)),
             ("est after", (T + timedelta(minutes=1)).astimezone(ny))]
    out = " | ".join(parse_headlines(rss(items), n=10, now=T))
    wrong = [t for t, _ in items if (t in out) != t.endswith("before")]
    if wrong:
        raise Violation(f"pubDates with a non-UTC offset compared wrongly ({wrong}): {out}")


run_checks([
    Check("D-PIT-1", "headlines after `now` are dropped", "now = 2025-11-20 21:30Z, items −40m / +9h / −2d",
          "only the two past items", drops_future),
    Check("D-PIT-2", "boundary: published at `now` is kept, one second later is not", "items at T and T+1s",
          "'exactly now' kept, 'one second later' dropped", boundary_kept),
    Check("D-PIT-3", "pubDates in other time zones are compared as instants",
          "items at T∓1m written in +09:00 and −05:00",
          "both 'before' items kept, both 'after' items dropped", offset_compared_as_instants),
])
