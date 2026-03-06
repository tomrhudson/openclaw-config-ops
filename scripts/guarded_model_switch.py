#!/usr/bin/env python3
"""
guarded_model_switch.py

Safe model switch wrapper for OpenClaw.
Use instead of /models to enforce preflight -> change -> smoke test -> confirm.
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'


def run(cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def emit(payload, json_only=False):
    if json_only:
        print(json.dumps(payload, indent=2))
    else:
        if payload.get('ok'):
            print(f"Guarded model switch: {payload.get('alias')} -> {payload.get('newOwner')}")
            print(f"Reason: {payload.get('reason')}")
            print(f"Inference policy: {payload.get('inferencePolicy')}")
            if payload.get('backup'):
                print(f"Backup: {payload.get('backup')}")
            smoke = payload.get('smoke', {})
            if smoke:
                print('Smoke checks:')
                for key, result in smoke.items():
                    status = 'PASS' if result.get('ok') else 'FAIL'
                    print(f"- {key}: {status}")
            print(f"Rollback: python3 {SCRIPT_DIR}/rollback_config.py --latest --yes")
        else:
            print(json.dumps(payload, indent=2))


def timestamp():
    return dt.datetime.now().strftime('%Y%m%d-%H%M%S')


def backup_file(path: Path):
    backup = path.parent / f"{path.name}.backup-{timestamp()}"
    shutil.copy2(path, backup)
    return backup


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def validate_json(path: Path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, None
    except Exception as e:
        return False, str(e)


def semantic_validate():
    proc = run(['openclaw', 'gateway', 'status'], check=False)
    stdout = proc.stdout or ''
    stderr = proc.stderr or ''
    invalid = 'Config invalid' in stdout or 'Config invalid' in stderr or 'Invalid config at' in stderr
    return {
        'ok': proc.returncode == 0 and not invalid,
        'commandOk': proc.returncode == 0,
        'configValid': not invalid,
        'stdout': stdout.strip(),
        'stderr': stderr.strip(),
    }


def get_models_map(data):
    return data.setdefault('agents', {}).setdefault('defaults', {}).setdefault('models', {})


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


def validate_target_model_exists(data, model):
    return model in get_models_map(data)


def clear_alias_from_all_models(data, alias):
    models = get_models_map(data)
    cleared = []
    for model_key, meta in models.items():
        if not isinstance(meta, dict):
            continue
        if meta.get('alias') == alias:
            del meta['alias']
            cleared.append(model_key)
    return cleared


def assign_alias_to_model(data, alias, model):
    models = get_models_map(data)
    if model not in models:
        raise KeyError(f'target model not found: {model}')
    if not isinstance(models[model], dict):
        models[model] = {}
    models[model]['alias'] = alias


def preflight(alias: str, model: str, reason: str):
    cmd = [
        str(SCRIPT_DIR / 'preflight_check.py'),
        '--change', f'Switch alias {alias} to model {model}',
        '--reason', reason,
        '--success', f'Alias {alias} resolves to {model} and responds',
        '--smoke-test', f'Run alias-uniqueness-check, model-alias-check, and inference-check for {model}',
        '--risk', 'medium',
        '--rollback', str(CONFIG_PATH) + '.backup-latest',
        '--require-model-exists', model,
        '--require-alias', alias,
        '--json',
    ]
    proc = run(cmd, check=False)
    try:
        return json.loads(proc.stdout) if proc.stdout else {'ok': False, 'error': proc.stderr or 'empty output'}
    except json.JSONDecodeError:
        return {'ok': False, 'error': proc.stderr or proc.stdout or 'unknown error'}


def smoke_test_alias_uniqueness(alias: str):
    proc = run([str(SCRIPT_DIR / 'smoke_test.py'), '--kind', 'alias-uniqueness-check', '--alias', alias], check=False)
    try:
        return json.loads(proc.stdout) if proc.stdout else {'ok': False, 'error': proc.stderr or 'empty output'}
    except json.JSONDecodeError:
        return {'ok': False, 'error': proc.stderr or proc.stdout or 'unknown error'}


def smoke_test_alias(alias: str, model: str):
    proc = run([str(SCRIPT_DIR / 'smoke_test.py'), '--kind', 'model-alias-check', '--alias', alias, '--model', model], check=False)
    try:
        return json.loads(proc.stdout) if proc.stdout else {'ok': False, 'error': proc.stderr or 'empty output'}
    except json.JSONDecodeError:
        return {'ok': False, 'error': proc.stderr or proc.stdout or 'unknown error'}


def smoke_test_inference(provider: str, model: str):
    proc = run([str(SCRIPT_DIR / 'smoke_test.py'), '--kind', 'inference-check', '--provider', provider, '--model', model], check=False)
    try:
        return json.loads(proc.stdout) if proc.stdout else {'ok': False, 'error': proc.stderr or 'empty output'}
    except json.JSONDecodeError:
        return {'ok': False, 'error': proc.stderr or proc.stdout or 'unknown error'}


def parse_model_ref(model: str):
    parts = model.split('/')
    if len(parts) >= 2:
        return parts[0], '/'.join(parts[1:])
    return None, model


def inference_policy_passes(result, policy):
    if policy == 'strict':
        return result.get('ok') and not result.get('classification')
    if policy == 'reachable':
        return result.get('ok') or result.get('classification') in ('auth-failed', 'reachable-auth-required')
    if policy == 'auth-ok':
        return result.get('ok') or result.get('classification') == 'auth-failed'
    return False


def update_alias_direct(alias: str, model: str):
    data = load_config()
    if not validate_target_model_exists(data, model):
        return {'ok': False, 'error': f'target model not found in agents.defaults.models: {model}'}

    old_owners = collect_alias_owners(data, alias)
    if len(old_owners) > 1:
        return {'ok': False, 'error': 'alias has multiple owners; refusing unsafe mutation', 'alias': alias, 'owners': old_owners}

    backup = backup_file(CONFIG_PATH)
    try:
        clear_alias_from_all_models(data, alias)
        assign_alias_to_model(data, alias, model)
        save_config(data)
        ok, err = validate_json(CONFIG_PATH)
        if not ok:
            shutil.copy2(backup, CONFIG_PATH)
            return {'ok': False, 'error': 'resulting JSON invalid; rolled back', 'detail': err, 'backup': str(backup)}
        semantic = semantic_validate()
        if not semantic['ok']:
            shutil.copy2(backup, CONFIG_PATH)
            return {'ok': False, 'error': 'semantic config validation failed; rolled back', 'backup': str(backup), 'semantic': semantic}
        new_owners = collect_alias_owners(load_config(), alias)
        return {'ok': True, 'alias': alias, 'oldOwners': old_owners, 'newOwner': model, 'ownersAfter': new_owners, 'backup': str(backup), 'semantic': semantic}
    except Exception as e:
        shutil.copy2(backup, CONFIG_PATH)
        return {'ok': False, 'error': str(e), 'backup': str(backup)}


def main():
    p = argparse.ArgumentParser(description='Guarded model switch for OpenClaw')
    p.add_argument('--alias', required=True, help='Alias to update (e.g., gpt)')
    p.add_argument('--model', required=True, help='Full model reference (e.g., openai/gpt-5.4)')
    p.add_argument('--reason', required=True, help='Why you are switching models')
    p.add_argument('--inference-policy', choices=['strict', 'reachable', 'auth-ok'], default='strict', help='How strict inference smoke validation should be')
    p.add_argument('--skip-preflight', action='store_true', help='Skip preflight (not recommended)')
    p.add_argument('--skip-smoke', action='store_true', help='Skip smoke test (not recommended)')
    p.add_argument('--dry-run', action='store_true', help='Show what would happen without changing')
    p.add_argument('--json', action='store_true', help='Emit machine-readable JSON only')
    args = p.parse_args()

    provider, model_id = parse_model_ref(args.model)
    if not provider:
        payload = {'ok': False, 'error': f'Could not parse provider from model: {args.model}'}
        emit(payload, args.json)
        return 1

    preflight_result = None
    if not args.skip_preflight:
        preflight_result = preflight(args.alias, args.model, args.reason)
        if not preflight_result.get('ok'):
            payload = {'ok': False, 'stage': 'preflight', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'preflight': preflight_result}
            emit(payload, args.json)
            return 2

    current_data = load_config()
    existing_owners = collect_alias_owners(current_data, args.alias)
    if len(existing_owners) > 1:
        payload = {'ok': False, 'stage': 'precheck-alias-uniqueness', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'owners': existing_owners, 'error': 'alias has multiple owners; resolve manually before switching', 'preflight': preflight_result}
        emit(payload, args.json)
        return 3

    if args.dry_run:
        payload = {'ok': True, 'stage': 'dry-run', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'inferencePolicy': args.inference_policy, 'existingOwners': existing_owners, 'preflight': preflight_result, 'next': 'would update alias and run alias-uniqueness, alias-resolution, and inference smoke tests'}
        emit(payload, args.json)
        return 0

    change_result = update_alias_direct(args.alias, args.model)
    if not change_result.get('ok'):
        payload = {'ok': False, 'stage': 'update-alias', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'inferencePolicy': args.inference_policy, 'preflight': preflight_result, 'change': change_result}
        emit(payload, args.json)
        return 4

    smoke = {}
    if not args.skip_smoke:
        smoke['uniqueness'] = smoke_test_alias_uniqueness(args.alias)
        if not smoke['uniqueness'].get('ok'):
            payload = {'ok': False, 'stage': 'smoke-alias-uniqueness', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'inferencePolicy': args.inference_policy, 'preflight': preflight_result, 'change': change_result, 'smoke': smoke}
            emit(payload, args.json)
            return 5

        smoke['alias'] = smoke_test_alias(args.alias, args.model)
        if not smoke['alias'].get('ok'):
            payload = {'ok': False, 'stage': 'smoke-alias-resolution', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'inferencePolicy': args.inference_policy, 'preflight': preflight_result, 'change': change_result, 'smoke': smoke}
            emit(payload, args.json)
            return 6

        smoke['inference'] = smoke_test_inference(provider, model_id)
        if not inference_policy_passes(smoke['inference'], args.inference_policy):
            payload = {'ok': False, 'stage': 'smoke-inference', 'alias': args.alias, 'requestedModel': args.model, 'reason': args.reason, 'inferencePolicy': args.inference_policy, 'preflight': preflight_result, 'change': change_result, 'smoke': smoke}
            emit(payload, args.json)
            return 7

    payload = {
        'ok': True,
        'alias': args.alias,
        'requestedModel': args.model,
        'newOwner': args.model,
        'reason': args.reason,
        'inferencePolicy': args.inference_policy,
        'backup': change_result.get('backup'),
        'oldOwners': change_result.get('oldOwners', []),
        'ownersAfter': change_result.get('ownersAfter', []),
        'preflight': preflight_result,
        'change': change_result,
        'smoke': smoke,
        'rollback': f'python3 {SCRIPT_DIR}/rollback_config.py --latest --yes',
    }
    emit(payload, args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
