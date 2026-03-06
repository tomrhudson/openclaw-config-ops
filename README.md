# openclaw-config-ops

`openclaw-config-ops` is an OpenClaw skill for **safer configuration changes**.

It adds operational discipline around `openclaw.json` changes:
- audit config hygiene
- enforce preflight checks
- run guarded changes with backups and rollback paths
- validate syntax and runtime semantics
- verify aliases, providers, fallbacks, and inference paths

## Quick Start: Guarded Model Switch

The easiest way to use this skill is via a shell alias:

```bash
alias switch-model='/path/to/openclaw-config-ops/scripts/guarded_model_switch.py'
```

Reload your shell:
```bash
source ~/.zshrc
```

Run a guarded switch:
```bash
switch-model --alias gpt --model openai/gpt-5.4 --reason "testing new model"
```

## Inference policy modes

`guarded_model_switch.py` now supports explicit inference policy control:

- `--inference-policy strict`
  - requires successful authenticated inference
- `--inference-policy reachable`
  - accepts authenticated success or reachability/auth-required classification
- `--inference-policy auth-ok`
  - accepts authenticated success or auth failure classification

Example:
```bash
switch-model --alias gpt --model openai/gpt-5.4 --reason "cutover" --inference-policy strict
```

## What this repo contains

- `SKILL.md` — runtime skill guidance
- `scripts/audit_openclaw_config.py` — config audit + semantic/runtime validation + corruption detection
- `scripts/preflight_check.py` — preflight checklist gate
- `scripts/change_runner.py` — guarded config mutation runner with rollback on semantic failure
- `scripts/rollback_config.py` — safe rollback helper
- `scripts/smoke_test.py` — smoke test suite
- `scripts/guarded_model_switch.py` — guarded alias switcher with policy controls
- `scripts/export_public_release.py` — one-command export/scan/package helper
- `references/rules.md` — condensed rules

## Notable safety features

- duplicate alias ownership detection
- dot-split model-key corruption detection
- runtime semantic validation using `openclaw gateway status`
- backup-first mutation flow
- rollback on invalid JSON
- rollback on semantic config failure

## License

MIT License — see LICENSE.
