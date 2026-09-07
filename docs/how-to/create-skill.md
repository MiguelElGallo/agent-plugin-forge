# Create a new skill

Author the skill in a separate staging directory. Put `SKILL.md` at its root and make the directory name match the frontmatter name.

```text
release-notes/
└── SKILL.md
```

Start with the smallest complete skill:

```markdown
---
name: release-notes
description: Create release notes from reviewed commits and pull requests.
---

Use repository evidence to draft concise release notes. Do not invent changes.
```

Add `scripts/`, `references/`, or `assets/` only when the instructions need them. Test deterministic scripts in the staging workspace before intake. The importer deliberately does not execute them.

## Record the source and license

Before importing, place the applicable license text in the source repository and commit the reviewed skill and license there. Keep the skill in a subdirectory so its imported tree excludes Git internals:

```text
source-repo/
├── .git/
├── LICENSE
└── release-notes/
    └── SKILL.md
```

If this is your first source repository, initialize Git in `source-repo/` and configure your Git author identity first. Keep this source checkout separate from the Forge destination checkout. Import only `source-repo/release-notes/`: Forge traverses the selected directory, including hidden and ignored files, rather than exporting only Git-tracked files. For a skill already at a repository root, stage a clean export of its reviewed files outside the checkout before intake.

From the source repository, inspect the state and record the commit:

```bash
git status --short
git rev-parse HEAD
```

The skill and license should have no uncommitted changes or untracked additions. Use the full commit ID for `--revision`, the source repository URL or absolute local repository path for `--origin`, and `release-notes` for `--source-subpath` in this example. Pass the license's SPDX identifier with `--license` and `source-repo/LICENSE` as an absolute path with `--license-file`.

Forge records your declared revision and hashes the copied files; it does not fetch the revision to prove those files match it. Verify that match during review. If license evidence is missing or unclear, resolve it before import.

Then follow [Import an existing skill](import-skill.md) from the Forge checkout. Use the Forge repository as `origin` only when the skill was authored here; otherwise preserve its actual source and license.
