# Intake and provenance

## Source modes

- **Skill directory:** pass the directory whose root contains `SKILL.md`.
- **Lone skill file:** pass the file named `SKILL.md`; Forge creates the destination directory.
- **Existing Agent Plugin:** pass the plugin root. If it has several immediate skills, add `--source-skill NAME`.
- **Remote Git source:** clone to a separate temporary directory, resolve the exact commit or tree, inspect the selected local content, and then import it.

Forge deliberately does not fetch URLs. Separating retrieval from import keeps network access, credentials, ref resolution, and source selection visible.

## License evidence

Do not apply this repository's MIT license to third-party content. Confirm the applicable upstream license, record its SPDX expression, and pass the local license or notice text with `--license-file`. Forge copies and hashes that evidence inside the distributed plugin. Stop when copying rights are unclear.

## Provenance fields

Record:

- canonical HTTPS/SSH source URL, absolute local path, or precise local-origin identifier; never place credentials, query tokens, or fragments in provenance;
- a full immutable Git object ID or `sha256:<content digest>`;
- source subpath and import date;
- SPDX license and its evidence file;
- transformations, normally empty for a byte-identical import.

Forge computes per-file hashes, executable-mode bits, and the deterministic content-tree hash. The reviewed plan binds those values plus all destination and metadata choices.

## Review boundaries

Forge rejects root escapes, links, junctions, special files, case-fold collisions, oversized content, common secrets, duplicate destinations, invalid frontmatter, and ambiguous plugin sources. MCP validation additionally rejects unsafe commands, paths, URLs, headers, and missing packaged commands.

These checks reduce mistakes; they are not a malware scanner or sandbox. Review all executable and instructional content before merging.
