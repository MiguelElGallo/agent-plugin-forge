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

Then follow [Import an existing skill](import-skill.md). Use the forge repository as `origin` only when the skill was genuinely authored here; otherwise preserve its actual source and license.
