# Startup report shows a different signal than the engine actually executes

**Observed.** When `ai-trader run` starts, it prints a one-time snapshot ("시작 현황") with
each symbol's current rule signal. For an income ETF I hold (e.g. JEPQ), the snapshot showed
a trend-strategy signal, but the engine then acted on the relaxed income-ETF rule for the same
bars. The startup report and the executed decision disagree, so I cannot trust the report.

**Expected.** For every symbol, the rule signal shown in the startup report must be the same
signal `step_symbol` would act on for the same bars and position. In particular, income ETFs
must use the relaxed income-ETF rule in both places, and regular stocks must keep using the
configured strategy in both places.
