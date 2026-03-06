# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows semantic-style release tags where practical.

## [1.0.0] - 2026-03-06

### Added
- Initial public release of `openclaw-config-ops`
- `audit_openclaw_config.py` for config hygiene, alias integrity, unresolved model refs, backup presence, and corruption detection
- `preflight_check.py` for enforcing backup/change-control workflow before edits
- `change_runner.py` for guarded config mutation with backup creation and rollback on validation failure
- `rollback_config.py` for safe backup listing and restoration
- `smoke_test.py` for runtime, alias, provider, fallback, reachability, and inference checks
- `guarded_model_switch.py` for safer alias switching with inference-policy control
- `export_public_release.py` for one-command export, sanitation scan, and packaging
- public README, ROADMAP, release tag, GitHub Release, and `.skill` release artifact

### Security
- Public repo export sanitized before release
- Repo contents and git history scanned for obvious secret/token patterns before publishing the release
