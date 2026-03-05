# OpenClaw Config Ops Rules

## Core Rules
- Back up `openclaw.json` before meaningful edits.
- Prefer minimal, additive changes.
- Test exact changed behavior after restart/reload.
- Keep aliases explicit for promoted models.
- Avoid inline plaintext secrets in config when safer loading patterns exist.
- Detect defaults/fallbacks that reference undeclared models.

## Auditor Targets
The auditor should report at least:
1. Inline secret candidates (API keys, access tokens, bot tokens, auth material)
2. Missing or unusual backup state for `openclaw.json`
3. Aliases pointing at unknown model ids
4. Defaults/fallbacks/image model refs that do not resolve
5. Configured models with no alias when aliasing appears intentional
6. Notable mismatches between provider declarations and alias map

## Follow-on Automation Targets
- Preflight checklist gate ✅
- Automatic backup creation
- Minimal patch application path
- Restart + smoke-test helper
- Rollback shortcut
