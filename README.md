# openclaw-config-ops

`openclaw-config-ops` is an OpenClaw skill for **safer configuration changes**.

It provides lightweight tooling and workflow support for changing `openclaw.json` with better discipline:
- audit configuration hygiene
- enforce a preflight checklist
- run guarded config changes with backups and rollback paths
- run smoke tests after changes
- verify model aliases, providers, fallbacks, gateway status, and basic inference paths

## What This Repo Contains

This repo packages an OpenClaw skill with:
- `SKILL.md` — trigger description and workflow guidance
- `scripts/audit_openclaw_config.py` — config hygiene audit
- `scripts/preflight_check.py` — checklist gate before changes
- `scripts/change_runner.py` — guarded change runner
- `scripts/rollback_config.py` — safe rollback helper
- `scripts/smoke_test.py` — smoke tests for config operations
- `references/rules.md` — condensed operating rules

## Why This Exists

Changing OpenClaw configuration is easy to do badly:
- secrets get pasted into the wrong place
- aliases drift
- backups are skipped
- restarts happen without verification
- “should work” replaces actual testing

This skill adds process and tooling so config changes are:
- smaller
- safer
- easier to verify
- easier to roll back

## Current Capabilities

### 1. Config Audit
Audit `openclaw.json` for:
- inline secret candidates
- unresolved model references
- alias mismatches
- missing backups
- notable config hygiene issues

### 2. Preflight Enforcement
Require:
- change description
- reason
- success criteria
- smoke test
- backup presence
- rollback path

Optional strict mode adds stronger checks for high-risk changes.

### 3. Guarded Change Runner
Supports:
- timestamped backup creation
- minimal dotted-path JSON updates
- JSON validation
- automatic rollback if resulting JSON is invalid
- optional restart and smoke-test bookkeeping

### 4. Rollback Safety
Rollback helper supports:
- latest/specific backup selection
- dry-run mode
- explicit confirmation for live restore

### 5. Smoke Tests
Smoke tests currently cover:
- audit rerun
- gateway/schema status
- model alias checks
- provider checks
- provider reachability
- fallback checks
- authenticated inference checks

## Intended Environment

This skill is designed for OpenClaw environments that use a local config file at:

- `~/.openclaw/openclaw.json`

It assumes:
- Python 3 is available
- OpenClaw CLI is available for gateway-related checks
- the user understands the impact of live config changes

## Suggested Use

Typical workflow:
1. Run the auditor
2. Run preflight
3. Make a guarded change
4. Restart if needed
5. Run smoke tests
6. Roll back if verification fails

## Future Improvements

Potential next steps:
- richer schema-aware validation
- deeper provider-specific inference checks
- one-command alias → provider → model verification
- fallback failover testing
- tighter policy controls for high-risk changes