# Metadata and provenance

## Portable identity

`plugins/<plugin>/plugin.json` is authoritative for plugin name, version, description, author, URLs, license, keywords, and Agent Plugins version. Its Agent Plugins 1.0 schema is closed. Skills, MCP servers, and category are not root manifest fields.

Every distributed forge plugin requires a semantic version and description.

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

The approval hash printed by `forge import` also binds the destination's current package state and catalog entry, version, author, category, license bytes and destination, source kind, selected source skill, provenance fields, content hashes, and executable modes. A changed plan must be reviewed again.
