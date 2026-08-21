# Trust model

Packaging is not trust. A valid plugin may still contain harmful instructions, scripts, MCP endpoints, or excessive permission requests.

The importer narrows accidental risk by staging local content, planning before writes, refusing symlinks and special files, checking path and case collisions, limiting size, scanning common secret patterns, preserving hashes, and never executing source content. Generation applies the same symlink boundary to its outputs and stages every client artifact before replacement. Reviewers still decide whether the source, license, behavior, network access, and permissions are acceptable.

Remote retrieval stays outside the importer so agents cannot hide ref resolution, credentials, or network access inside a copy command. CI uses no secrets on pull requests, has read-only repository permissions, and never runs imported scripts.
