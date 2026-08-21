# Import an existing skill

Stage remote sources at an immutable revision before this workflow. The forge accepts a local directory whose root contains `SKILL.md`.

```bash
uv run forge branch --plugin release-notes --skill release-notes

uv run forge import \
  --source /absolute/path/release-notes \
  --plugin release-notes \
  --category "Developer Tools" \
  --version 0.1.0 \
  --description "Create concise release notes from reviewed changes." \
  --author "Upstream Author" \
  --license MIT \
  --license-file /absolute/path/LICENSE \
  --origin https://github.com/example/repository \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --source-subpath skills/release-notes
```

Review the dry-run output and source. Repeat with `--apply --expected-sha256 HASH`, using the hash printed by the dry run, then run:

```bash
uv run forge generate
uv run forge check
```

The import fails rather than rewriting malformed frontmatter, mismatched names, unsafe file types, likely secrets, or an existing destination.
