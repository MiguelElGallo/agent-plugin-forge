# Create a new skill

Create the skill in a separate staging directory with `SKILL.md` at its root. Use lowercase hyphenated names and include `name` and `description` frontmatter.

```markdown
---
name: release-notes
description: Create release notes from reviewed commits and pull requests.
---

Use repository evidence to draft concise release notes.
```

Add only resources the skill needs, such as `scripts/`, `references/`, or `assets/`. Test deterministic scripts in the staging workspace, then follow [Import an existing skill](import-skill.md). Record the forge repository as the origin only when the skill was genuinely authored here.
