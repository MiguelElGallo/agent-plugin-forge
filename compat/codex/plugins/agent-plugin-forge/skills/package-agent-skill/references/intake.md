# Intake and provenance

## Source modes

- Skill directory: stage the directory whose root contains `SKILL.md` and import it directly.
- Lone `SKILL.md`: create a same-named staging directory and place the file there before import.
- Existing Agent Plugin: select one immediate child of its `skills/` directory. Importing an entire plugin is a separate migration decision.
- Remote Git source: clone into a temporary directory, resolve the exact commit, inspect the selected tree, and pass that local tree to the forge.

The forge deliberately does not fetch URLs. Separating retrieval from import makes network access, credentials, ref resolution, and review visible to the user.

## License evidence

Do not infer that this repository's MIT license applies to imported third-party content. Confirm the upstream license and pass the applicable local license text with `--license-file`; the forge copies and hashes it inside the distributed plugin. Record the SPDX identifier in the import request. Stop when copying rights are unclear.

## Provenance fields

Record:

- canonical source URL or a clear local-origin identifier;
- immutable Git commit/tree identifier or a content-addressed revision;
- source subpath;
- import date;
- SPDX license identifier;
- every imported file's SHA-256 and the deterministic tree SHA-256;
- transformations, which should normally be empty for a byte-identical import.

## Review boundaries

The importer rejects symlinks, special files, case-fold collisions, large trees, likely credential files, likely embedded secrets, duplicate destinations, and ambiguous skill structure. These checks reduce mistakes; they are not a malware scanner or a sandbox. Review all executable and instructional content before merging.
