# Add a skill to a bundle

Bundling is opt-in. Choose an existing destination plugin only when the skills form one coherent installable capability.

The existing bundle supplies its category, author, and distribution identity. Pass a new plugin version during import; the forge rejects an unchanged version.

```bash
uv run forge import \
  --source /absolute/path/second-skill \
  --plugin existing-plugin \
  --version 0.2.0 \
  --license Apache-2.0 \
  --license-file /absolute/path/LICENSE \
  --origin https://github.com/example/source \
  --revision 0123456789abcdef \
  --source-subpath skills/second-skill \
  --expected-sha256 HASH \
  --apply
```

Omit `--category`: existing bundles inherit it. Each bundled skill receives its own provenance record and retains its own upstream license.
