# Add a skill to a bundle

Bundling is opt-in. Choose an existing destination only when the skills form one coherent installable capability.

Create the new skill branch, plan the import, and omit `--category`. The existing bundle owns its category and author identity. Pass a strictly higher plugin version:

```bash
uv run forge branch --plugin existing-plugin --skill second-skill

uv run forge import \
  --source /absolute/path/second-skill \
  --plugin existing-plugin \
  --version 0.2.0 \
  --license Apache-2.0 \
  --license-file /absolute/path/LICENSE \
  --origin https://github.com/example/source \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --source-subpath skills/second-skill
```

Review the no-write plan, then repeat with `--expected-sha256 HASH --apply`.

Each bundled skill receives its own provenance record and applicable license evidence. Imported files do not inherit the repository's MIT license.
