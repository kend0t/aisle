Model gemini-3.8-flash, 17 clips, 3 repeats per reader. Labels: an independent frame-by-frame review by Claude (not human labels). Agreement counts only clips whose outcome the review could tell (8 of 17 could not be told from the clip).

| Metric | baseline | single | verified |
|---|---|---|---|
| Outcome agreement with labels | 0.889 | 0.889 | 0.889 |
| Behavior tag F1 | 0.0 | 0.754 | 0.635 |
| Same outcome on every repeat | 16 of 17 | 15 of 17 | 16 of 17 |
| Wrong reads that were flagged | 0 of 3 | 0 of 3 | 0 of 3 |
| Flagged reads that were wrong | None | None | None |
| Unclear clips that were flagged | 0 of 24 | 0 of 24 | 4 of 24 |
| Outcome contradicts own observations | 0 of 51 | 0 of 51 | 0 of 51 |
| Gemini calls per clip | 1.0 | 1.0 | 3.0 |
| Mean latency (ms) | 9009 | 14169 | 15337 |
| Cost per clip (USD, gemini-2.5-flash list prices (gemini-3.8-flash not listed)) | 0.00061 | 0.00099 | 0.003 |
