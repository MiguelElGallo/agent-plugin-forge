# Maintain an existing skill

Use this contributor workflow when the requested skill already exists in the selected Forge repository. `forge import` adds new destinations and deliberately refuses an existing `skills/<name>` directory, even with a higher version. Do not delete the destination or its provenance to bypass that refusal. Client plugin updates are a separate operation after publication.

For a request to check or review only, inspect and report without changing files. A contributor update needs authorization for the concrete source, destination, and proposed changes. It does not use the importer's approval hash. Preserve the selected private origin throughout checkout, review, and any approved publication.

## Prepare the revision

1. Bootstrap the selected origin as described in [publish.md](publish.md), or use its existing clean, current checkout. Record the origin and base revision.
2. Inspect the current skill, its provenance and license, and the proposed source revision. Test the author's own helpers in the source workspace when authorized; do not execute imported scripts or hooks during intake. Correct invalid third-party content in a separately reviewed source change.
3. Create `skill/<plugin>/<skill>` with `uv run forge branch --plugin NAME --skill NAME`. If the branch already exists, inspect its work instead of resetting it. Use a plugin-wide branch when the change includes shared runtime or MCP files.
4. After the contributor update is authorized, replace only the reviewed skill files and modes from the approved source. Retain the applicable license evidence, and remove obsolete files only when their removal is part of the reviewed revision.
5. Prepare a higher plugin version and a complete provenance update. Compare the packaged tree with the reviewed source; a matching hash records that comparison but does not establish trust in the content.

## Preview provenance for an authored revision

This example is for one authored skill in a single-skill plugin. Run it from the selected Forge checkout after staging the authorized source and license changes. Replace the example paths, identity, version, and license with reviewed values. For a bundle, also review the shared manifest and its license declarations.

The example prints candidate JSON without writing it. It uses a `sha256:` source revision for the exact reviewed source tree. Use a full immutable Git object ID instead only when you have verified that the source files match that object; do not label uncommitted edits with an older commit.

```bash
uv run python - <<'PY'
import hashlib
import json
from datetime import date
from pathlib import Path

from agent_plugin_forge.common import load_json, parse_semver, tree_hash
from agent_plugin_forge.filesystem import (
    file_hashes,
    inspect_regular_file,
    inspect_regular_tree,
)
from agent_plugin_forge.models import PortableManifest, ProvenanceRecord

plugin = Path("plugins/incident-summary")
skill = plugin / "skills/incident-summary"
source = Path("/absolute/path/to/skill-sources/skills/incident-summary")
source_license = Path("/absolute/path/to/skill-sources/LICENSE")
new_version = "0.2.0"
license_id = "MIT"  # Use the source's actual, approved license.

inspect_regular_tree(plugin, required_root_file="plugin.json", tree_label="Plugin")
files = file_hashes(skill, required_root_file="SKILL.md")
source_files = file_hashes(source, required_root_file="SKILL.md")
modes = {name: bool((skill / name).stat().st_mode & 0o111) for name in files}
source_modes = {name: bool((source / name).stat().st_mode & 0o111) for name in source_files}
if files != source_files or modes != source_modes:
    raise SystemExit("Packaged files or modes differ from the reviewed source")

record_path = plugin / "provenance/incident-summary.json"
record = load_json(record_path)
previous = ProvenanceRecord.model_validate(record)
evidence = plugin / previous.license_evidence.path
license_bytes = inspect_regular_file(source_license, file_label="Reviewed license")
if inspect_regular_file(evidence, file_label="Packaged license") != license_bytes:
    raise SystemExit("Packaged license differs from the reviewed evidence")

digest = tree_hash(files)
record.update(
    origin="https://github.company.example/platform/skill-sources.git",
    revision=f"sha256:{digest}",
    sourceSubpath="skills/incident-summary",
    importedAt=date.today().isoformat(),
    license=license_id,
    licenseEvidence={
        "path": previous.license_evidence.path,
        "sha256": hashlib.sha256(license_bytes).hexdigest(),
    },
    files=files,
    fileModes=modes,
    contentSha256=digest,
    transformations=[],
)
ProvenanceRecord.model_validate(record)

manifest = load_json(plugin / "plugin.json")
if parse_semver(new_version, label="New version") <= parse_semver(
    manifest["version"], label="Current version"
):
    raise SystemExit("The plugin version must increase")
manifest.update(version=new_version, license=license_id)
PortableManifest.model_validate(manifest)
print(json.dumps({"provenance": record, "manifest": manifest}, indent=2))
PY
```

Review the printed values against the source and intended destination. After approval within the contributor change, write those values to the existing provenance record and `plugin.json`, preserving their JSON field names. Do not run `forge import --apply` or present this preview as a hash-bound import plan.

## Validate and publish the contributor change

Run `uv run forge generate`, `uv run forge check`, Ruff lint and format checks, `uv run ty check`, `uv run pytest`, `uv run zensical build --clean --strict`, and `git diff --check`. Renderer golden tests use a fixed fixture; updating a real skill or plugin version does not require changing `tests/golden/`. Review the complete source-to-package diff and perform an authorized behavior check in the intended client.

Commit, push, and open a pull request only when those actions were authorized, against the selected origin. Merge is separate and requires authorization for the reviewed head SHA and green required checks. After merge, report the plugin version and the applicable commands for an existing installation:

```bash
codex plugin marketplace upgrade MARKETPLACE_NAME
codex plugin add PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin update PLUGIN_NAME@MARKETPLACE_NAME
```

Derive the marketplace name from the selected repository. VS Code users run **Extensions: Check for Extension Updates** and choose **Update** when it is offered, then confirm the skill in a new chat.
