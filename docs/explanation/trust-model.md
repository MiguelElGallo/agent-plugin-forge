# Trust model

Packaging is not trust. A schema-valid plugin may still contain harmful instructions, executable code, an unsafe MCP service, or behavior that asks for excessive permissions.

## What the forge prevents

During intake and generation, Forge rejects:

- path traversal, resolved-root escapes, symlinks, junctions, and special files;
- case-fold collisions that behave differently across operating systems;
- unexpected destination overwrite;
- files and trees over configured size limits;
- common secret filenames, private keys, GitHub tokens, and AWS access-key patterns;
- malformed Agent Skills frontmatter and duplicate skill identities;
- invalid semantic versions, SPDX expressions, provenance, or license hashes;
- unsafe MCP commands, working directories, URLs, headers, root overrides, and missing packaged commands;
- stale or partially published generated output.

The importer plans before writing and binds the full approved plan. It copies content without running scripts or hooks. Generation builds all client artifacts in a temporary tree, validates them, then replaces outputs as a transaction. Failure tests prove rollback restores the previous state.

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
