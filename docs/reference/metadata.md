# Metadata and provenance

## Portable identity

`plugins/<plugin>/plugin.json` is authoritative for plugin name, version, description, author, URLs, license, keywords, and Agent Plugins version. Its Agent Plugins 1.0 schema is closed. Skills, MCP servers, and category are not root manifest fields.

Every distributed forge plugin requires a semantic version and description.

Forge also requires an SPDX license expression. These are Forge distribution requirements beyond the portable schema; see [Standards and Forge policy](standards.md).

## Catalog metadata

`catalog/plugins.json` adds only distribution information:

- marketplace identity and version;
- category;
- whether to list the portable package in the Codex marketplace.

Both client marketplaces are derived separately from the catalog and portable manifests. Their schemas are materially different and are never treated as interchangeable.

## Per-skill provenance

Each `provenance/<skill>.json` records:

- canonical origin and immutable revision;
- source subpath and import date;
- SPDX license expression;
- license-evidence path and SHA-256;
- every copied file's SHA-256 and executable-mode bit;
- deterministic content-tree SHA-256;
- declared transformations.

Source origins accept credential-free HTTPS, SSH, scp-style SSH, file URLs, absolute local paths, or simple local identifiers. Forge rejects embedded credentials, query tokens, fragments, Git remote-helper syntax, control characters, and ambiguous relative paths before provenance can be written.

The approval hash printed by `forge import` also binds the selected Forge repository URL, the complete catalog bytes, the destination's current package state, version, author, category, license bytes and destination, source kind, selected source skill, normalized provenance fields, content hashes, and executable modes. A changed plan must be reviewed again.
