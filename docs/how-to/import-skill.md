# Import an existing skill

Use this guide when the source is already local and reviewed. The importer accepts three shapes:

- a directory with `SKILL.md` at its root;
- a lone file named `SKILL.md`;
- an existing plugin directory, with `--source-skill NAME` when it contains multiple skills.

Remote sources must first be cloned or downloaded to a separate staging directory at an immutable revision. The importer never fetches or executes source content.

## Create the scoped branch

```bash
uv run forge branch --plugin release-notes --skill release-notes
```

## Plan without writing

```bash
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

For an existing plugin with several skills, point `--source` at the plugin root and add `--source-skill release-notes`.

## Apply the exact plan

Review the source, license, destination, and plan output. Repeat the same command with:

```text
--expected-sha256 HASH_FROM_THE_PLAN --apply
```

Any change to source bytes, executable modes, license evidence, metadata, or destination produces a different plan hash and blocks the apply.

## Check it

```bash
uv run forge generate
uv run forge check
```

The import fails with an exact diagnostic instead of rewriting malformed frontmatter, mismatched names, unsafe paths, links, junctions, special files, likely secrets, oversized files, or an existing destination.
