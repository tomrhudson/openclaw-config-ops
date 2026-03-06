#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
WORKSPACE = Path.home() / '.openclaw' / 'workspace'
DEFAULT_PUBLIC_DIR = WORKSPACE / 'public-repos' / 'openclaw-config-ops'
DEFAULT_DIST_DIR = WORKSPACE / 'dist-public'
PACKAGE_SCRIPT = Path('/opt/homebrew/lib/node_modules/openclaw/skills/skill-creator/scripts/package_skill.py')

README_TEXT = """# openclaw-config-ops

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
switch-model --alias gpt --model openai/gpt-5.4 --reason \"testing new model\"
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
switch-model --alias gpt --model openai/gpt-5.4 --reason \"cutover\" --inference-policy strict
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
"""

ROADMAP_TEXT = """# ROADMAP

## Completed
- auditor
- preflight gate
- guarded change runner
- rollback helper
- smoke tests
- guarded model switch
- duplicate alias detection
- dot-split model-key corruption detection
- semantic config validation
- inference policy modes
- one-command public export and packaging

## Next candidates
- provider-aware alias normalization
- richer fallback/failover testing
- more precise provider-model catalog reconciliation
- split docs further into USAGE vs CONTRIBUTING if needed
"""

LICENSE_TEXT = """MIT License

Copyright (c) 2026 Tom Hudson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

CHANGELOG_PLACEHOLDER = '{"note": "Intentionally blank for public distribution. Local change logs should not be published."}\n'

DEFAULT_SCAN_PATTERNS = [
    r'sk-[A-Za-z0-9_-]+',
    r'ops_[A-Za-z0-9_-]+',
    r'sm_[A-Za-z0-9_-]+',
]


def run(cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def clean_python_artifacts(root: Path):
    for pycache in root.rglob('__pycache__'):
        shutil.rmtree(pycache, ignore_errors=True)
    for pattern in ('*.pyc', '*.pyo'):
        for f in root.rglob(pattern):
            try:
                f.unlink()
            except FileNotFoundError:
                pass


def sanitize_public_dir(public_dir: Path):
    clean_python_artifacts(public_dir)
    write_text(public_dir / 'README.md', README_TEXT)
    write_text(public_dir / 'ROADMAP.md', ROADMAP_TEXT)
    write_text(public_dir / 'LICENSE', LICENSE_TEXT)
    write_text(public_dir / 'references' / 'change-log.jsonl', CHANGELOG_PLACEHOLDER)


def build_scan_patterns(extra_patterns):
    patterns = list(DEFAULT_SCAN_PATTERNS)
    patterns.extend(extra_patterns)
    return patterns


def scan_public_dir(public_dir: Path, patterns):
    issues = []
    for file_path in public_dir.rglob('*'):
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding='utf-8', errors='ignore')
        hits = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                hits.append({'pattern': pattern, 'match': match.group(0)[:120]})
        if hits:
            issues.append({'file': str(file_path), 'hits': hits})
    return issues


def package_skill(skill_dir: Path, dist_dir: Path):
    dist_dir.mkdir(parents=True, exist_ok=True)
    proc = run(['python3', str(PACKAGE_SCRIPT), str(skill_dir), str(dist_dir)], check=False)
    return {
        'ok': proc.returncode == 0,
        'code': proc.returncode,
        'stdout': proc.stdout.strip(),
        'stderr': proc.stderr.strip(),
        'artifact': str(dist_dir / f'{skill_dir.name}.skill'),
    }


def sync_skill_to_public(skill_dir: Path, public_dir: Path):
    if public_dir.exists():
        shutil.rmtree(public_dir)
    shutil.copytree(skill_dir, public_dir)


def main():
    p = argparse.ArgumentParser(description='Export openclaw-config-ops for public release')
    p.add_argument('--json', action='store_true', help='Emit JSON only')
    p.add_argument('--no-package', action='store_true', help='Skip packaging step')
    p.add_argument('--public-dir', default=str(DEFAULT_PUBLIC_DIR))
    p.add_argument('--dist-dir', default=str(DEFAULT_DIST_DIR))
    p.add_argument('--scan-pattern', action='append', default=[], help='Additional regex pattern to scan for in public export')
    args = p.parse_args()

    public_dir = Path(args.public_dir).expanduser()
    dist_dir = Path(args.dist_dir).expanduser()
    patterns = build_scan_patterns(args.scan_pattern)

    clean_python_artifacts(SKILL_DIR)
    sync_skill_to_public(SKILL_DIR, public_dir)
    sanitize_public_dir(public_dir)
    issues = scan_public_dir(public_dir, patterns)
    if issues:
        payload = {
            'ok': False,
            'stage': 'scan',
            'issues': issues,
            'publicDir': str(public_dir),
        }
        print(json.dumps(payload, indent=2))
        return 1

    package_result = None
    if not args.no_package:
        package_result = package_skill(SKILL_DIR, dist_dir)
        if not package_result['ok']:
            payload = {
                'ok': False,
                'stage': 'package',
                'publicDir': str(public_dir),
                'distDir': str(dist_dir),
                'package': package_result,
            }
            print(json.dumps(payload, indent=2))
            return 2

    payload = {
        'ok': True,
        'publicDir': str(public_dir),
        'distDir': str(dist_dir),
        'scan': 'PUBLIC_SANITATION_OK',
        'patternsUsed': patterns,
        'package': package_result,
        'artifact': str(dist_dir / f'{SKILL_DIR.name}.skill') if not args.no_package else None,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print('Public release export complete')
        print(f'Public dir: {public_dir}')
        print('Scan: PUBLIC_SANITATION_OK')
        if package_result:
            print(f'Artifact: {payload["artifact"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
