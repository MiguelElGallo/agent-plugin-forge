# Release input contract

The UTF-8 JSON object contains a nonempty, single-line `version` and a nonempty `changes` array. Every change has:

- `section`: `highlights`, `changes`, or `upgrade_notes`;
- `text`: a nonempty, single-line string, preserved exactly;
- `references`: an array of nonempty, single-line strings, preserved in supplied order.

The Markdown uses `# Release VERSION`, followed by nonempty sections in the order Highlights, Changes, Upgrade notes. Changes keep their input order within each section. References appear in parentheses after their change text.

The JSON index has `schema_version: 1`, the version, total change count, a count for all three sections, and distinct reference IDs in first-seen input order. Files use UTF-8 and LF line endings. The renderer creates a new output directory and refuses any existing file or directory at that path.
