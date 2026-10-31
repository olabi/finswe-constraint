"""Market-calendar payloads (dates disjoint from the repo's fixtures)."""


def _s(day, a, b):
    return {"startTime": f"{day}T{a}+09:00", "endTime": f"{day}T{b}+09:00"}


def kr(day_prev="2025-11-20", day_next="2025-11-24"):
    def block(d):
        return {"date": d, "integrated": {
            "preMarket": _s(d, "08:00:00", "08:50:00"),
            "regularMarket": _s(d, "09:00:00", "15:30:00"),
            "afterMarket": _s(d, "15:40:00", "20:00:00")}}
    return {"today": {"date": "2025-11-22", "integrated": None},
            "previousBusinessDay": block(day_prev), "nextBusinessDay": block(day_next)}


def us():
    def block(d, d2):
        return {"date": d,
                "dayMarket": _s(d, "10:00:00", "17:00:00"),
                "preMarket": _s(d, "18:00:00", "23:30:00"),
                "regularMarket": {"startTime": f"{d}T23:30:00+09:00", "endTime": f"{d2}T06:00:00+09:00"},
                "afterMarket": {"startTime": f"{d2}T06:00:00+09:00", "endTime": f"{d2}T09:00:00+09:00"}}
    return {"today": {"date": "2025-11-22", "dayMarket": None, "preMarket": None,
                      "regularMarket": None, "afterMarket": None},
            "previousBusinessDay": block("2025-11-21", "2025-11-22"),
            "nextBusinessDay": block("2025-11-24", "2025-11-25")}


def labels(sessions):
    return sorted({s[2] for s in (sessions or [])})
