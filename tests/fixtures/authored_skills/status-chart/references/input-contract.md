# Status input contract

The UTF-8 JSON object contains a nonempty, single-line `title` and between one and sixteen `statuses`. Each status has a unique, nonempty, single-line `label` and an integer `count` from zero to one million. Boolean counts are invalid. Labels and counts retain their supplied order.

The SVG has an accessible title and description, a label and count for every category, and one bar per category. Bar widths are integer-scaled against the largest count; an all-zero input produces zero-width bars. XML-sensitive characters are escaped.

The JSON summary has `schema_version: 1`, the original title, ordered labels and counts, total count, and maximum count. Files use UTF-8 and LF line endings. The renderer creates a new output directory and refuses any existing file or directory at that path.
