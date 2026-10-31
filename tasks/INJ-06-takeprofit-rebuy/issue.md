# Take-profit sells, then the bot buys straight back

**Observed.** With `--take-profit` on a core holding, the bot sold at +20% and re-bought
the same shares minutes later at an even higher price. It paid two fees and ended up
holding the same position at a worse cost.

**Expected.** After a take-profit sale, re-buying that symbol **on the same day** is
blocked unless the price falls below `sale price × (1 − take_profit_rebuy_buffer)`. On the
next day the block lifts and the normal accumulate rule applies again.
