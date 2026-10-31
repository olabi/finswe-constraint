# Closed-market message spams the log every poll

**Observed.** When the market is closed, the engine prints the same "market closed / next
open" line on every polling iteration, flooding the log overnight.

**Expected.** Print the closed-market line once when the market becomes closed (or when the
reported next-open time changes), and stay quiet on repeated polls while nothing changed.

(The line in question is the existing "전체 시장 마감 …" message; keep its wording.)
