# News replay leaks headlines from the future

**Observed.** When news is evaluated as of a past time (`parse_headlines(xml, now=T)`, as
in replays and checks of past decisions), headlines **published after T** still come back,
labelled with a negative or odd relative age. Decisions "at T" then use information that
did not exist yet.

**Expected.** `parse_headlines(..., now=T)` must drop every item whose pubDate is later
than T. Items at or before T behave as today (ordering, `max_age_hours`, relative-age
labels).
