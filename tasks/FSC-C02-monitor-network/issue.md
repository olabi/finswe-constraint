# `monitor` dies on a transient network error

**Observed.** `ai-trader monitor` runs a polling loop. A single transient network failure
(connection reset / timeout from the broker API) raises out of the loop and the whole
monitor process exits, so nothing is watched until I notice and restart it.

**Expected.** A transient network error inside one polling iteration should be reported as
a warning, and the loop should continue on the next interval. Other errors keep their
current behavior.
