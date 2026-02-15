# Unit tests and blocking time in days/hours

## Summary
- **Unit tests** for all data-processing and calculation functions (`process_issue`, `blocker_info_to_dict`, `blocker_category_from_comment`, `comments_text`, `format_blocking_time`). `main()` is not tested.
- **CLI `--time-unit`**: output blocking time in days (default) or hours.
- **Data model**: blocking time is stored in the dict **in seconds**; conversion to days/hours happens only when formatting output (print, CSV, xlsx).

## What's tested (29 tests)

### `process_issue`
- Empty result when no Flagged changes; one/two blocker cycles; flag set but not removed (fallback to last status change). Dict stores `Time Blocked` in seconds.

### `blocker_info_to_dict`
- `Time Blocked` always in seconds (integer and fractional intervals). Flag times, category, comments, `Flag was not removed`.

### `blocker_category_from_comment`
- Pattern matching, comment time, custom patterns (`#\w+`, `\{...\}`, `[...]`), empty pattern.

### `comments_text`
- Filtering by time range; empty/single comment.

### `format_blocking_time`
- Conversion from seconds to days or hours for output; fractional and zero.

## Running tests
```bash
python3 -m unittest test_jira_blocker_analyser -v
```
Dependencies (jira, pandas) are mocked; no numpy required.

## Branch
`feature/blocker-tests-and-time-unit`
