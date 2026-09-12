# Trust model

Packaging is not trust. A schema-valid plugin may still contain harmful instructions, executable code, an unsafe MCP service, or behavior that asks for excessive permissions.

## What the forge prevents

Forge's intake and repository-validation gates reject:

- path traversal, resolved-root escapes, symlinks, junctions, and special files;
- case-fold collisions that behave differently across operating systems;
- unexpected destination overwrite;
- files and trees over configured size limits;
- common secret filenames, private keys, GitHub tokens, and AWS access-key patterns;
- malformed Agent Skills frontmatter and duplicate skill identities;
- invalid semantic versions, SPDX expressions, provenance, or license hashes;
- unsafe MCP commands, working directories, URLs, headers, root overrides, and missing packaged commands;
- stale or partially published generated output.

The importer plans before writing and binds the full approved plan. It copies content without running scripts or hooks. Generation prepares validated client outputs in a temporary tree before replacing the destination files. Failure tests cover ordinary rollback and preservation of recovery files when restoration itself fails. Keep any reported recovery directory until the repository has been restored; see [rollback recovery](../how-to/troubleshoot.md#marketplace-generation-reports-a-rollback-failure).

File inspection captures bounded bytes and executable modes from the same verified file descriptor. Source metadata, file hashes, the aggregate content digest, and copying use those captured bytes; license hashing uses the bytes that passed inspection. Apply checks a fresh captured source against the reviewed file map before copying it. Changes detected during a file read fail closed. This is not an atomic snapshot of an entire directory tree, and it does not lock source or checkout directories against concurrent writers.

Untrusted values in human-readable diagnostics have terminal controls escaped so filenames cannot clear the screen or inject new diagnostic lines. This display protection does not rename files, change their contents, or establish that imported instructions are safe.

## Authorization boundary

An initial request to publish starts review only. The installed skill may create a local checkout and plan, but it must stop before applying the plan or changing GitHub state. The user approves the exact plan hash and the proposed fork, push, and pull-request actions. Merge remains separate and requires the reviewed head SHA plus green required checks.

For alternate origins, the bootstrap helper verifies the selected remote and a reusable checkout's branch, cleanliness, and origin. Publication derives its target and authentication host from that origin rather than assuming GitHub.com.

## What reviewers still decide

Automated checks do not prove that prompt instructions are honest, a script is benign, an HTTPS endpoint is trustworthy, or an upstream license grants the intended rights. Reviewers must examine:

- every instruction and executable file;
- MCP endpoints, network behavior, authentication, and data exposure;
- source ownership and immutable revision;
- license and notice obligations;
- requested client permissions and runtime dependencies.

Remote retrieval remains outside the importer. This keeps credentials, network access, ref resolution, and the selected source tree visible as a separate operation. Stage remote content locally, inspect it, and then pass only the selected local skill to Forge.

## CI boundary

Pull-request workflows use read-only repository permissions, receive no secrets, never use `pull_request_target`, never execute imported scripts, and never commit generated output. GitHub Pages deploys only from `main`.
