# A historical run reads a 10-Q filed after its run date

**Observed.** In a historical run dated `2024-07-03`, the fundamentals analyst called
`get_income_statement(curr_date="2024-07-3")` (the model dropped the day's leading zero).
SEC EDGAR then served the Q2 10-Q **filed on 2024-07-23**, twenty days after the run
date, and its figures reached the final decision. With `curr_date="2024-07-03"` the same
run correctly sees only filings made on or before 2024-07-03.

**Expected.** A run dated D must never receive data filed after D, whatever form of the
date the model passes to a tool (`2024-07-3`, `2024-7-3`, `2024-07-03`, …). Filings made
on or before D are still served as before.
