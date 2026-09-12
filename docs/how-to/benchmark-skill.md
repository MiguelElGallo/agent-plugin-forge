# Benchmark the skill workflow

Check the workflow at three levels: deterministic CLI behavior, an agent following the shipped instructions, and installation in the intended client. A fast import does not establish that an agent selects the right workflow or that an installed skill behaves correctly.

## Repeat the local benchmark

From a development checkout:

```bash
uv sync --locked
uv run python benchmarks/skill_workflow.py \
  --runs 5 --sizes 1 100 1000 \
  --output /absolute/path/to/forge-benchmark.json
```

The harness creates disposable local Git repositories and inert, authored skills. Each size includes one `SKILL.md`; the remaining files are small text assets. It runs the shipped bootstrap helper with an explicit local origin and isolated settings, creates a skill branch, prepares and repeats a read-only import plan, refuses changed source, applies the reviewed plan, generates and validates both client indexes, refuses a duplicate destination, and checks the committed branch scope. It never executes imported content or contacts a hosted Git remote. Unexpected command results stop the run.

The JSON contains every sample, per-stage medians, Forge and Python versions, and the operating system. Timings include process startup with warm dependency and filesystem caches. They exclude fixture preparation, network, model reasoning, human review, client installation, and the full test suite. There are no machine-dependent pass/fail timing thresholds.

### Recorded local result

The current release is `1.0.0`. The measurements below are historical `0.0.2` results; the report and raw data retain the version actually measured and do not claim a new performance result for 1.0.0.

The `0.0.2` candidate was measured on macOS arm64 with Python 3.12.13, using five fresh fixtures per size. The [raw results](../assets/benchmarks/macos-python312-0.0.2.json) retain all samples. Values below are median milliseconds, rounded to the nearest millisecond.

| Files in one skill | Bootstrap | Review plan | Apply | Generate | Validate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 94 | 107 | 113 | 105 | 105 |
| 100 | 107 | 118 | 149 | 119 | 146 |
| 1,000 | 111 | 254 | 493 | 247 | 490 |

Bootstrap copies the small Forge fixture, so source-skill size mainly affects the later stages. This measures file-count scaling within a skill, not throughput across a large catalog or a before/after speedup.

## Evaluate the instructions

Give an independent agent a realistic request and the current shipped skill, then record the steps it actually takes. Include a check-only request, a private destination, missing license evidence, changed source after review, multiple source skills requiring selection, and maintenance of an existing skill. Preserve command output and the final diff; distinguish fixture setup errors from workflow errors.

For `0.0.2`, five bounded CLI conformance scenarios passed: read-only planning, private-origin binding, missing-license refusal, changed-source refusal, and explicit multi-skill selection. A separate forward walkthrough followed the shipped maintenance example, changed an authored review footer, raised its plugin version, refreshed provenance and generated metadata, and left a four-file diff for review. It preserved the private origin and passed the full repository gate. Its private transport was simulated locally; these few scenarios do not establish a model success rate.

## Test a real client

Use a disposable private repository and an isolated client configuration. Add at least three plugins, include a multi-skill bundle, install and invoke every skill, then update one plugin. Compare installed versions and complete file hashes before and after; confirm that the other plugins stayed unchanged.

The recorded Copilot acceptance added three plugins containing four new skills, installed and invoked all four, then updated only `team-review` from `0.1.0` to `0.1.1`. Its marker changed from V1 to V2 while the other installed package hashes stayed equal. Individual installs took 0.985–1.061 seconds, and marketplace refresh plus the selected update took 2.328 seconds in that single small-fixture run. These observations are not a performance guarantee. Exact clients and qualification boundaries are recorded in [Client compatibility evidence](../reference/compatibility.md).
