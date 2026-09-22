---
name: release-digest
description: Create deterministic Markdown release notes and a JSON index from reviewed changes.
---

# Release digest

Use this authored test fixture when asked to turn a reviewed JSON change list into release artifacts.

1. Read the supplied JSON and [input contract](references/input-contract.md). Ask for missing release information; do not invent changes or references.
2. Review [the renderer](scripts/render.py) before running it. Run it only as an explicitly requested behavior check, never during Forge intake or import.
3. Use the selected Python interpreter to run `scripts/render.py --input INPUT.json --output-dir OUTPUT_DIRECTORY` from this skill directory. The output directory must not already exist.
4. Report the absolute paths of `release-notes.md` and `release-index.json`. Preserve the supplied change text and reference IDs.

The [sample input](assets/input.json) has deterministic [expected Markdown](assets/expected/release-notes.md) and [expected JSON](assets/expected/release-index.json). This fixture makes no network requests and reads no clock or credentials. Write artifacts only to the requested output directory.
