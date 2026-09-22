---
name: status-chart
description: Create a deterministic SVG status chart and JSON summary from reviewed category counts.
---

# Status chart

Use this authored test fixture when asked to produce a status chart from a reviewed JSON count list.

1. Read the supplied JSON and [input contract](references/input-contract.md). Ask for missing counts; never estimate or invent them.
2. Review [the renderer](scripts/render.py) before running it. Run it only as an explicitly requested behavior check, never during Forge intake or import.
3. Use the selected Python interpreter to run `scripts/render.py --input INPUT.json --output-dir OUTPUT_DIRECTORY` from this skill directory. The output directory must not already exist.
4. Report the absolute paths of `status.svg` and `status-summary.json`, including the supplied counts and their total.

The [sample input](assets/input.json) includes Unicode, XML-sensitive text, and a zero-count category. Compare with the [expected SVG](assets/expected/status.svg) and [expected summary](assets/expected/status-summary.json). This fixture makes no network requests and reads no clock or credentials. Write artifacts only to the requested output directory.
