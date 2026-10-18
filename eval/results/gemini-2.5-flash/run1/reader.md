Model gemini-2.5-flash, 17 clips, 3 repeats per reader. Labels: an independent frame-by-frame review by Claude (not human labels). Agreement counts only clips whose outcome the review could tell (8 of 17 could not be told from the clip).

| Metric | baseline | single | verified |
|---|---|---|---|
| Outcome agreement with labels | 0.741 | 0.704 | 0.852 |
| Behavior tag F1 | 0.0 | 0.693 | 0.641 |
| Same outcome on every repeat | 10 of 17 | 11 of 17 | 15 of 17 |
| Wrong reads that were flagged | 0 of 7 | 0 of 8 | 1 of 4 |
| Flagged reads that were wrong | None | None | 0.143 |
| Unclear clips that were flagged | 0 of 24 | 0 of 24 | 7 of 24 |
| Outcome contradicts own observations | 0 of 51 | 0 of 51 | 0 of 51 |
| Gemini calls per clip | 1.0 | 1.0 | 3.0 |
| Mean latency (ms) | 8588 | 8238 | 14472 |
| Cost per clip (USD) | 0.00125 | 0.00152 | 0.00458 |
