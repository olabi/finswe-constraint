# US stocks show a KOSPI crash siren

**Observed.** The run log appends a market-stress siren (🚨 sidecar / circuit-breaker
estimate) to each symbol's poll line. On a day the Korean market sold off hard, my US
positions (SCHD) showed the 🚨 KOSPI siren even though US markets were calm. The siren is
always computed from the KODEX200 ETF (069500), whatever market the symbol trades in.

**Expected.**
- The siren for a symbol must be computed from that symbol's own market proxy:
  KR symbols → KODEX200 (`069500`), US symbols → VOO (S&P 500).
- A crash in one market must not flag symbols of the other market.
- Keep the existing thresholds and siren format. `_market_stress()` called without a
  symbol must keep working as before (KR proxy).
