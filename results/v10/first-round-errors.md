# v10 · gate rounds that ended in `error` (PUB-21)

Excerpts from the v10 traces (Kaggle kernel `kmmmvs/finswe-constraint-pilot` v10). Traces themselves
are not committed. `observed` is the text the gate returned to the agent; "submitted" lines are the
date-handling lines of `tradingagents/dataflows/vendors/sec_edgar.py` in that submission (`_as_of`).
Every final, passing patch fixed `_as_of` in the **sec_edgar vendor**; none touched `date_window.py`.

Each exception was raised by the agent's own submitted code on the unpadded date the check feeds it
(`'2025-3-7'`, `'2025-03-7'`); none came from the environment. The gate message carried the scenario and
expected value along with the exception.

| run · round | checks in `error` | `observed` (as returned) | submitted (date handling) | final passing fix |
|---|---|---|---|---|
| C_domain s0 · r1 | D-PIT-SEC-1, -2 | `AttributeError: type object 'datetime.datetime' has no attribute 'datetime'` | `try: as_of_date = date.fromisoformat(as_of_date)…`<br>`except ValueError: as_of_date = datetime.datetime.strptime(as_of_date, "%Y-%m-%d")…` (the module imports `from datetime import datetime`) | sec_edgar `_as_of`: same try/except, fallback corrected to `datetime.strptime(...)` |
| C_domain s1 · r1 | D-PIT-SEC-1, -2 | `ValueError: Invalid isoformat string: '2025-3-7'` / `'2025-03-7'` | `- as_of_date = as_of_date or datetime.now()…`<br>`+ as_of_date = date.fromisoformat(as_of_date).isoformat() if as_of_date else …` | sec_edgar `_as_of`: on failure, split on `-` and pad to `f"{y:04d}-{m:02d}-{d:02d}"` |
| C_domain s2 · r1 | D-PIT-SEC-1, -2 | `ValueError: Invalid isoformat string: '2025-3-7'` / `'2025-03-7'` | `+ as_of_date = date.fromisoformat(as_of_date).isoformat() if as_of_date else …` | sec_edgar `_as_of`: `datetime.strptime(as_of_date, "%Y-%m-%d").date().isoformat()` (r3) |
| C_domain s2 · r2 | D-PIT-SEC-1, -2, -3 (+ G-REGRESSION fail, same exception) | `AttributeError: type object 'datetime.datetime' has no attribute 'datetime'` | `+ as_of_date = datetime.datetime.strptime(as_of_date, "%Y-%m-%d").date().isoformat() if as_of_date else …` | as above: `datetime.datetime.strptime` → `datetime.strptime` |
| C_know s0 · r1 | D-IMPORT (+ G-REGRESSION "skipped: syntax errors first") | `SyntaxError: unexpected character after line continuation character` (G-SYNTAX: `sec_edgar.py:191`) | `+ as_of_date = (as_of_date or datetime.now()…)\n    # Ensure … try:\n        datetime.strptime(…` (literal `\n` escapes written into one line) | sec_edgar `_as_of`: `parts = as_of_date.split("-")` → `f"{parts[0].zfill(4)}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"` |
| C_know s1 · r1 | D-PIT-SEC-1, -2 (+ G-REGRESSION fail: `TypeError: '>' not supported between instances of 'datetime.date' and 'str'`) | `ValueError: Invalid isoformat string: '2025-3-7'` / `'2025-03-7'` | `+ if date.fromisoformat(fact["filed"]) > as_of_date …`<br>`+ as_of_date = date.fromisoformat(as_of_date or datetime.now()…)` | sec_edgar: new `_normalize_date()` (split + `zfill(2)`), applied to `as_of_date` in `_as_of` (r2 was an empty patch → plain `fail`; r3 passed) |

Takeaway for §5.4: on the first submission, the domain gate mostly reported an exception the
scenario triggered, not a `fail` verdict. It drove the fix all the same: 3/3 C_domain and 3/3 C_know
ended with a passing gate and resolved. The `date.fromisoformat` attempt passed the visible tests in
C_domain s1/s2, so only the domain scenario caught it. The same call appears in all
three B_generic final patches (0/3 resolved).
