# openclaw-config-ops

`openclaw-config-ops` is an OpenClaw skill for **safe, repeatable configuration changes**.

It turns fragile `openclaw.json` edits into a guarded workflow with:
- auditing before changes
- preflight checks before mutation
- backup-first config edits
- JSON + runtime semantic validation
- smoke tests for aliases, providers, fallbacks, and inference
- rollback support when a change goes sideways

## Why this exists

OpenClaw config changes are easy to get wrong.

A small edit can silently introduce:
- broken model aliases
- drift between configured aliases and real providers
- invalid nested keys from dotted-path writes
- restarts without verification
- secret exposure in the wrong place

This skill exists to make those operations boring, deterministic, and recoverable.

## What’s included

- `SKILL.md` — skill guidance and workflow
- `scripts/audit_openclaw_config.py` — audit config hygiene, alias integrity, model refs, inline secrets, and corruption patterns
- `scripts/preflight_check.py` — require change intent, success criteria, smoke tests, backup, and rollback path
- `scripts/change_runner.py` — guarded config mutation with backup and rollback on invalid JSON or semantic failure
- `scripts/rollback_config.py` — list, inspect, and restore backups safely
- `scripts/smoke_test.py` — runtime, alias, provider, fallback, reachability, and inference checks
- `scripts/guarded_model_switch.py` — safer alias-switch workflow with inference policy control
- `scripts/export_public_release.py` — one-command export, sanitation scan, and package workflow
- `references/rules.md` — condensed operating rules

## Core capabilities

### 1. Config audit
Detects:
- inline secret candidates
- duplicate alias ownership
- invalid alias entries
- unresolved model references
- aliases pointing to unknown models
- missing backups
- dot-split model-key corruption patterns

### 2. Preflight enforcement
Requires operators to define:
- the change
- the reason
- what success looks like
- what smoke test proves it
- what backup exists
- how rollback works

### 3. Guarded change execution
`change_runner.py` provides:
- timestamped backup creation
- controlled JSON mutation
- syntax validation
- semantic/runtime validation
- rollback on failure
- optional restart and smoke-test bookkeeping

### 4. Guarded model switching
`guarded_model_switch.py` adds a safer alternative to ad hoc alias changes.

It supports:
- alias ownership checks
- target-model existence validation
- direct config mutation instead of fragile generic dotted writes
- post-change alias verification
- post-change inference verification
- inference policy modes:
  - `strict`
  - `reachable`
  - `auth-ok`

### 5. Public release automation
`export_public_release.py` handles:
- public repo export sync
- sanitation of public docs/changelog
- cache cleanup
- leak scanning
- `.skill` packaging

## Quick start

### Audit first
```bash
python3 scripts/audit_openclaw_config.py
```

### Run a guarded model switch
```bash
python3 scripts/guarded_model_switch.py \
  --alias gpt \
  --model openai/gpt-5.4 \
  --reason "cutover to latest GPT model" \
  --inference-policy strict
```

### Export a public release
```bash
python3 scripts/export_public_release.py --json
```

## Opinionated operating model

This repo assumes:
- backup before mutation
- validate after mutation
- fail closed on unsafe alias state
- prefer explicit smoke tests over wishful thinking
- treat runtime semantic failure as real failure

## License

MIT License — see `LICENSE`.
