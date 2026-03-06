# Contributing

Thanks for contributing.

## Ground rules

This project exists to make OpenClaw configuration changes safer, more repeatable, and easier to verify.

If you contribute here, optimize for:
- safety before convenience
- explicit validation over assumptions
- rollback-first thinking
- machine-readable output where useful
- minimal surprise for operators

## Development expectations

Before proposing changes:
1. keep changes scoped and reviewable
2. avoid hardcoding private/local environment details into public files
3. keep public exports sanitized
4. prefer additive improvements over clever rewrites
5. preserve backward compatibility where practical for operator-facing flags

## Repo hygiene

Do not commit:
- secrets
- private tokens
- local operator-specific environment details
- private logs or local state artifacts
- `__pycache__`, `.pyc`, or other generated junk

## Good contribution targets

Examples of useful improvements:
- better audit precision
- stronger smoke tests
- clearer docs
- safer release automation
- better provider/model normalization

## Release expectations

Before publishing a release:
1. verify public repo contents
2. run a sanitation scan
3. package the `.skill`
4. verify no obvious secrets exist in tracked files or history
5. attach the packaged artifact to the GitHub Release
