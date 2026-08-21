# Security policy

## Supported version

The latest commit on `main` is supported during the initial `0.x` development line.

## Reporting

Do not open a public issue for a vulnerability or exposed credential. Use GitHub's private vulnerability reporting for this repository.

## Trust boundary

Imported skills contain instructions and may contain executable scripts. The forge copies and validates structure without executing imported content. Its checks for symlinks, special files, size, case collisions, and common secrets reduce accidental risk but do not establish that a skill is safe. Review source, license, prompts, scripts, network behavior, and requested permissions before merging or installing it.
