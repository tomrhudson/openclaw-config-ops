#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
BACKUP_GLOB_PREFIX = 'openclaw.json.backup-'


def parse_args():
    p = argparse.ArgumentParser(description='Preflight checklist gate for OpenClaw config changes')
    p.add_argument('--target', default=str(CONFIG_PATH), help='Target file/service being changed')
    p.add_argument('--change', required=True, help='What is changing')
    p.add_argument('--reason', required=True, help='Why the change is needed')
    p.add_argument('--success', required=True, help='What success looks like')
    p.add_argument('--smoke-test', required=True, dest='smoke_test', help='Exact smoke test to run after change')
    p.add_argument('--risk', choices=['low', 'medium', 'high'], required=True)
    p.add_argument('--rollback', help='Known rollback path or backup target')
    p.add_argument('--secrets-involved', action='store_true', help='Flag if secrets/auth material are involved')
    p.add_argument('--allow-plaintext-secrets', action='store_true', help='Acknowledge plaintext secret risk explicitly')
    p.add_argument('--strict', action='store_true', help='Enable stricter policy checks for higher-risk changes')
    p.add_argument('--json', action='store_true', help='Emit JSON only')
    return p.parse_args()


def latest_backup(target: Path):
    parent = target.parent
    prefix = target.name + '.backup-'
    matches = sorted([p for p in parent.iterdir() if p.name.startswith(prefix)])
    return matches[-1] if matches else None


def main():
    args = parse_args()
    target = Path(args.target).expanduser()

    checks = []

    checks.append({
        'name': 'target_exists_or_is_known',
        'ok': target.exists() or str(target) == str(CONFIG_PATH),
        'detail': str(target)
    })

    checks.append({
        'name': 'change_defined',
        'ok': bool(args.change.strip()),
        'detail': args.change
    })
    checks.append({
        'name': 'reason_defined',
        'ok': bool(args.reason.strip()),
        'detail': args.reason
    })
    checks.append({
        'name': 'success_defined',
        'ok': bool(args.success.strip()),
        'detail': args.success
    })
    checks.append({
        'name': 'smoke_test_defined',
        'ok': bool(args.smoke_test.strip()),
        'detail': args.smoke_test
    })

    backup = latest_backup(target)
    checks.append({
        'name': 'backup_present',
        'ok': backup is not None,
        'detail': str(backup) if backup else None
    })

    checks.append({
        'name': 'rollback_known',
        'ok': bool((args.rollback or '').strip()) or backup is not None,
        'detail': args.rollback or (str(backup) if backup else None)
    })

    if args.secrets_involved:
        checks.append({
            'name': 'plaintext_secret_acknowledged',
            'ok': args.allow_plaintext_secrets,
            'detail': 'Secrets involved; explicit acknowledgment required if plaintext handling is expected'
        })

    if args.strict or args.risk == 'high':
        checks.append({
            'name': 'strict_requires_explicit_rollback',
            'ok': bool((args.rollback or '').strip()),
            'detail': args.rollback or 'High-risk/strict mode requires explicit rollback path'
        })
        checks.append({
            'name': 'strict_requires_existing_target',
            'ok': target.exists(),
            'detail': str(target)
        })

    failures = [c for c in checks if not c['ok']]
    result = {
        'ok': len(failures) == 0,
        'risk': args.risk,
        'target': str(target),
        'checks': checks,
        'failures': failures,
        'next': 'proceed' if len(failures) == 0 else 'stop'
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Preflight: {'PASS' if result['ok'] else 'FAIL'}")
        print(f"Target: {result['target']}")
        print(f"Risk: {result['risk']}")
        for c in checks:
            mark = 'OK' if c['ok'] else 'FAIL'
            print(f"- [{mark}] {c['name']}: {c['detail']}")
        if failures:
            print('\nStop. Missing preflight requirements.')
        else:
            print('\nProceed. Preflight complete.')
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
