#!/usr/bin/env python3
import json
import glob
import re
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
BACKUP_GLOB = str(Path.home() / '.openclaw' / 'openclaw.json.backup-*')
SECRET_KEYS = {'apikey', 'api_key', 'token', 'bottoken', 'secret'}
DIGIT_KEY_RE = re.compile(r'^\d+$')


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def walk(obj, path='$'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}"
            yield child, v
            yield from walk(v, child)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{path}[{i}]"
            yield child, v
            yield from walk(v, child)


def qualified_model_id(provider_name, model_id):
    return f"{provider_name}/{model_id}"


def normalize_declared_ref(ref, providers):
    parts = ref.split('/') if isinstance(ref, str) else []
    if len(parts) >= 3 and parts[0] in providers:
        return ref
    if len(parts) == 2 and parts[0] in providers:
        return ref
    return f"openrouter/{ref}"


def model_catalog(data):
    providers = data.get('models', {}).get('providers', {})
    catalog = set()
    provider_models = {}
    for provider_name, provider in providers.items():
        models = provider.get('models', [])
        ids = []
        for model in models:
            mid = model.get('id')
            if not mid:
                continue
            full = qualified_model_id(provider_name, mid)
            catalog.add(full)
            ids.append(full)
        provider_models[provider_name] = ids
    return catalog, provider_models


def collect_aliases(data):
    return data.get('agents', {}).get('defaults', {}).get('models', {})


def collect_alias_owners(data):
    models = collect_aliases(data)
    owners = {}
    invalid_entries = []
    for model_key, meta in models.items():
        if not isinstance(meta, dict):
            invalid_entries.append({'model': model_key, 'entryType': type(meta).__name__})
            continue
        alias = meta.get('alias')
        if alias:
            owners.setdefault(alias, []).append(model_key)
    return owners, invalid_entries


def detect_dot_split_corruption(aliases):
    findings = []
    for model_key, meta in aliases.items():
        if not isinstance(meta, dict):
            continue
        digit_children = sorted(k for k in meta.keys() if isinstance(k, str) and DIGIT_KEY_RE.fullmatch(k))
        if not digit_children:
            continue
        provider_prefix, sep, base_model = model_key.partition('/')
        reconstructed = []
        for child in digit_children:
            reconstructed.append(f"{provider_prefix}/{base_model}.{child}" if sep else f"{model_key}.{child}")
        findings.append({
            'type': 'dot_split_model_key_corruption',
            'severity': 'critical',
            'model': model_key,
            'digitChildren': digit_children,
            'likelyIntendedKeys': reconstructed,
            'message': 'Model entry contains numeric child keys that suggest dotted model ids were split into nested paths.'
        })
    return findings


def collect_model_refs(data):
    defaults = data.get('agents', {}).get('defaults', {})
    refs = []
    model = defaults.get('model', {})
    primary = model.get('primary')
    if primary:
        refs.append(('agents.defaults.model.primary', primary))
    for i, item in enumerate(model.get('fallbacks', [])):
        refs.append((f'agents.defaults.model.fallbacks[{i}]', item))
    image_model = defaults.get('imageModel', {})
    primary = image_model.get('primary')
    if primary:
        refs.append(('agents.defaults.imageModel.primary', primary))
    for i, item in enumerate(image_model.get('fallbacks', [])):
        refs.append((f'agents.defaults.imageModel.fallbacks[{i}]', item))
    heartbeat = defaults.get('heartbeat', {})
    hb_model = heartbeat.get('model')
    if hb_model:
        refs.append(('agents.defaults.heartbeat.model', hb_model))
    return refs


def looks_like_secret(path, value):
    leaf = path.split('.')[-1].lower().replace('_', '')
    if leaf not in SECRET_KEYS:
        return False
    if not isinstance(value, str):
        return False
    return len(value.strip()) > 12


def gateway_semantic_check():
    import subprocess
    proc = subprocess.run(['openclaw', 'gateway', 'status'], capture_output=True, text=True)
    stderr = proc.stderr or ''
    stdout = proc.stdout or ''
    invalid = 'Config invalid' in stderr or 'Config invalid' in stdout or 'Invalid config at' in stderr
    return {
        'ok': proc.returncode == 0 and not invalid,
        'commandOk': proc.returncode == 0,
        'configValid': not invalid,
        'stdout': stdout.strip(),
        'stderr': stderr.strip(),
    }


def add(severity_bucket, item_type, **kwargs):
    item = {'type': item_type, 'severity': severity_bucket}
    item.update(kwargs)
    return item


def main():
    if not CONFIG_PATH.exists():
        print(json.dumps({'ok': False, 'error': f'missing config: {CONFIG_PATH}'}))
        return 1

    data = load_json(CONFIG_PATH)
    catalog, provider_models = model_catalog(data)
    providers = set(provider_models.keys())
    aliases = collect_aliases(data)
    alias_owners, invalid_alias_entries = collect_alias_owners(data)
    refs = collect_model_refs(data)

    findings = []
    warnings = []
    infos = []

    backups = sorted(glob.glob(BACKUP_GLOB))
    if backups:
        infos.append(add('info', 'backup_count', count=len(backups), latest=backups[-1]))
    else:
        warnings.append(add('warning', 'missing_backup', message='No openclaw.json backups found'))

    for path, value in walk(data):
        if looks_like_secret(path, value):
            findings.append(add('critical', 'inline_secret_candidate', path=path))

    findings.extend(detect_dot_split_corruption(aliases))

    semantic = gateway_semantic_check()
    if not semantic['ok']:
        findings.append(add('critical', 'semantic_config_invalid', detail={
            'commandOk': semantic['commandOk'],
            'configValid': semantic['configValid']
        }))
        infos.append(add('info', 'semantic_check_output', stdout=semantic['stdout'], stderr=semantic['stderr']))

    for ref_path, ref in refs:
        qualified_ref = normalize_declared_ref(ref, providers)
        if qualified_ref not in catalog:
            warnings.append(add('warning', 'unresolved_model_ref', path=ref_path, value=ref, qualified=qualified_ref))

    for model_key, meta in aliases.items():
        if not isinstance(meta, dict):
            warnings.append(add('warning', 'invalid_alias_entry', model=model_key, entryType=type(meta).__name__))
            continue
        provider_guess = normalize_declared_ref(model_key, providers)
        if provider_guess not in catalog:
            warnings.append(add('warning', 'alias_points_to_unknown_model', model=model_key, qualified=provider_guess, alias=meta.get('alias')))

    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            findings.append(add('critical', 'duplicate_alias_owner', alias=alias, owners=owners))

    if invalid_alias_entries:
        infos.append(add('info', 'invalid_alias_entries', count=len(invalid_alias_entries), entries=invalid_alias_entries))

    aliased = {k for k, v in aliases.items() if isinstance(v, dict) and v.get('alias')}
    unaliased_models = sorted(m for m in catalog if m not in aliased)
    if unaliased_models:
        infos.append(add('info', 'models_without_alias', count=len(unaliased_models), models=unaliased_models))

    summary = {
        'critical': len([x for x in findings if x.get('severity') == 'critical']),
        'warning': len(warnings),
        'info': len(infos),
    }

    result = {
        'ok': True,
        'config': str(CONFIG_PATH),
        'providers': sorted(provider_models.keys()),
        'modelCount': len(catalog),
        'summary': summary,
        'findings': findings,
        'warnings': warnings,
        'info': infos,
        'aliasOwners': alias_owners,
        'semanticCheck': {
            'ok': semantic['ok'],
            'commandOk': semantic['commandOk'],
            'configValid': semantic['configValid'],
        }
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
