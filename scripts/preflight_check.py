#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'


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
    p.add_argument('--require-model-exists', help='Require a specific model key to exist in agents.defaults.models')
    p.add_argument('--require-alias', help='Inspect current ownership for a specific alias')
    p.add_argument('--json', action='store_true', help='Emit JSON only')
    return p.parse_args()


def latest_backup(target: Path):
    parent = target.parent
    prefix = target.name + '.backup-'
    matches = sorted([p for p in parent.iterdir() if p.name.startswith(prefix)])
    return matches[-1] if matches else None


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_models_map(data):
    return data.get('agents', {}).get('defaults', {}).get('models', {})


def collect_alias_owners(data, alias=None):
    models = get_models_map(data)
    owners = {}
    for model_key, meta in models.items():
        if not isinstance(meta, dict):
            continue
        model_alias = meta.get('alias')
        if not model_alias:
            continue
        owners.setdefault(model_alias, []).append(model_key)
    if alias is not None:
        return owners.get(alias, [])
    return owners


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

    if args.require_model_exists or args.require_alias:
        try:
            data = load_config()
        except Exception as e:
            checks.append({
                'name': 'config_loadable_for_requirements',
                'ok': False,
                'detail': str(e)
            })
            data = None

        if data is not None and args.require_model_exists:
            models = get_models_map(data)
            checks.append({
                'name': 'required_model_exists',
                'ok': args.require_model_exists in models,
                'detail': args.require_model_exists
            })

        if data is not None and args.require_alias:
            owners = collect_alias_owners(data, args.require_alias)
            checks.append({
                'name': 'required_alias_inspected',
                'ok': True,
                'detail': {
                    'alias': args.require_alias,
                    'owners': owners,
                    'ownerCount': len(owners)
                }
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
