---
name: openclaw-config-ops
description: Safely inspect, audit, and change OpenClaw configuration and model/provider setup. Use when working with `openclaw.json`, validating config hygiene, enforcing backup/change-control flow, checking aliases/provider routing/fallbacks, or preparing guarded config edits and smoke tests.
---

# OpenClaw Config Ops

Use this skill for guarded operations around `~/.openclaw/openclaw.json` and related OpenClaw runtime config.

## Quick Start: Guarded Model Switch

The easiest way to use this skill is via the `switch-model` shell alias.

### Setup

Add to your shell profile:
```bash
alias switch-model='/path/to/openclaw-config-ops/scripts/guarded_model_switch.py'
```

### Usage
```bash
switch-model --alias gpt --model openai/gpt-5.4 --reason "testing new model"
```

This runs: preflight → alias update → smoke tests → confirmation.

## Workflow

1. **Audit first**
   - Run `scripts/audit_openclaw_config.py` before proposing risky edits.
   - Use it to detect obvious SOP violations: inline secrets, missing aliases, questionable model references, and lack of matching provider/model declarations.

2. **Back up before edits**
   - Create a timestamped backup of `openclaw.json` before any modification.
   - Preserve the rollback path in the final note.

3. **Make the smallest viable change**
   - Prefer additive model/provider changes.
   - Add a new model and explicit alias before promoting defaults.

4. **Validate after edits**
   - Use OpenClaw config tooling where available.
   - Confirm the changed path specifically: provider, alias, fallback, or routing.

5. **Restart once, then smoke test**
   - Restart only if needed.
   - Test the exact changed behavior, not a nearby one.

## Current bundled resources

### scripts/audit_openclaw_config.py
Audit `openclaw.json` against core SOP rules:
- inline secret exposure candidates
- alias coverage for configured models
- duplicate alias ownership detection
- invalid alias-entry detection
- dot-split model-key corruption detection (e.g. `openai/gpt-5` with child keys `2`, `4`)
- aliases pointing at undeclared models
- default/fallback/image model references that do not resolve cleanly
- config backups present for the primary config file

### scripts/preflight_check.py
Gate config changes behind a minimal checklist:
- target identified
- change, reason, success condition, and smoke test defined
- backup present
- rollback known
- optional target-model existence verification
- optional alias ownership inspection
- explicit acknowledgment when secrets/plaintext handling is involved
- optional strict mode for high-risk changes

### scripts/change_runner.py
Run a guarded config-change flow:
- create timestamped backup
- apply minimal dotted-path JSON sets (supports bracket notation for keys with `/` or `.`)
- validate JSON after changes
- roll back automatically if JSON becomes invalid
- optionally restart OpenClaw
- optionally run a smoke test
- append structured change log

### scripts/rollback_config.py
Restore `openclaw.json` from a specific or latest backup.
- supports `--list`
- supports `--json`
- supports `--dry-run`
- requires `--yes` for live restore

### scripts/smoke_test.py
Run lightweight smoke tests for config changes:
- audit rerun
- gateway status check
- runtime check (`runtime-check`; `schema-check` retained as deprecated alias)
- alias uniqueness verification
- model alias verification
- provider presence/model-count verification
- fallback reference verification
- provider reachability check via provider `/models` endpoint (treats 401/403 as reachable/auth-required)
- authenticated inference check via provider `/chat/completions`
  - handles provider-specific token parameter differences
  - classifies auth failures separately from bad request payloads
- handler-based dispatch for easier extension

### scripts/guarded_model_switch.py
End-to-end guarded model alias switcher.
- Use via shell alias: `switch-model`
- Enforces: preflight → direct config mutation → smoke test → confirm
- Refuses unsafe mutation if an alias has multiple owners
- Clears old alias owner(s) and assigns the new owner directly in config
- Runs alias uniqueness, alias resolution, and inference smoke tests
- Supports `--json` for machine-readable output

### references/rules.md
Condensed rules and implementation targets derived from `SOP-Change-Control.md`.

## Build direction

Current implementation covers **auditing**, **preflight gating**, and a hardened **guarded change runner** with live validation and authenticated inference testing. Next iterations should add:
- richer schema-aware validation using dedicated config tooling
- alias-to-provider resolution helpers for one-command end-to-end checks
- richer smoke-test kinds for actual fallback failover behavior
