# Ctrl+C prints a traceback instead of exiting quietly

**Observed.** Pressing Ctrl+C while a command is running (for example at the LIVE
confirmation prompt) dumps a Python `KeyboardInterrupt` traceback.

**Expected.** `ai-trader` should catch the interrupt in its CLI entry point, print a short
message, and exit with status **130** (the conventional code for SIGINT), with no traceback.
