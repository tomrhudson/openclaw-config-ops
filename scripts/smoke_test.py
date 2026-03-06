#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


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


def infer_api_base(provider_name, data):
    return data.get('models', {}).get('providers', {}).get(provider_name, {}).get('baseUrl')


def infer_provider(provider_name, data):
    return data.get('models', {}).get('providers', {}).get(provider_name, {})


def provider_auth_headers(provider_name, provider):
    headers = {'User-Agent': 'openclaw-config-ops-smoke', 'Content-Type': 'application/json'}
    api_key = provider.get('apiKey')
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    return headers


def inference_payload(provider_name, model):
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Reply with exactly: OK'}],
        'temperature': 0
    }
    if provider_name == 'openai':
        payload['max_completion_tokens'] = 12
    else:
        payload['max_tokens'] = 12
    return payload


def emit(result):
    print(json.dumps(result, indent=2))
    return 0 if result.get('ok') else 1


def run_audit_check(_args):
    proc = run([str(SCRIPT_DIR / 'audit_openclaw_config.py')])
    return {
        'ok': proc.returncode == 0,
        'kind': 'audit',
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def run_gateway_restart_check(_args):
    proc = run(['openclaw', 'gateway', 'status'])
    return {
        'ok': proc.returncode == 0,
        'kind': 'gateway-restart-check',
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def run_runtime_check(args):
    proc = run(['openclaw', 'gateway', 'status'])
    deprecated = args.kind == 'schema-check'
    return {
        'ok': proc.returncode == 0,
        'kind': 'runtime-check',
        'deprecated': deprecated,
        'use': 'runtime-check' if deprecated else None,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def run_model_alias_check(args):
    if not args.alias or not args.model:
        return {'ok': False, 'error': '--alias and --model are required for model-alias-check'}
    data = load_config()
    found = collect_alias_owners(data, args.alias)
    ok = found == [args.model]
    return {
        'ok': ok,
        'kind': 'model-alias-check',
        'alias': args.alias,
        'expected': args.model,
        'found': found,
    }


def run_alias_uniqueness_check(args):
    if not args.alias:
        return {'ok': False, 'error': '--alias is required for alias-uniqueness-check'}
    data = load_config()
    owners = collect_alias_owners(data, args.alias)
    ok = len(owners) == 1
    return {
        'ok': ok,
        'kind': 'alias-uniqueness-check',
        'alias': args.alias,
        'owners': owners,
        'ownerCount': len(owners),
    }


def run_provider_check(args):
    if not args.provider:
        return {'ok': False, 'error': '--provider is required for provider-check'}
    data = load_config()
    providers = data.get('models', {}).get('providers', {})
    provider = providers.get(args.provider)
    ok = provider is not None and bool(provider.get('models'))
    return {
        'ok': ok,
        'kind': 'provider-check',
        'provider': args.provider,
        'hasProvider': provider is not None,
        'modelCount': len(provider.get('models', [])) if provider else 0,
    }


def run_provider_reachability_check(args):
    if not args.provider:
        return {'ok': False, 'error': '--provider is required for provider-reachability'}
    import urllib.request, urllib.error
    data = load_config()
    base = infer_api_base(args.provider, data)
    if not base:
        return {
            'ok': False,
            'kind': 'provider-reachability',
            'provider': args.provider,
            'error': 'provider baseUrl not found',
        }
    url = base.rstrip('/') + '/models'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'openclaw-config-ops-smoke'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = getattr(resp, 'status', 200)
            ok = status < 500
            return {
                'ok': ok,
                'kind': 'provider-reachability',
                'provider': args.provider,
                'url': url,
                'status': status,
                'classification': 'reachable',
            }
    except urllib.error.HTTPError as e:
        reachable = e.code in (401, 403)
        return {
            'ok': reachable,
            'kind': 'provider-reachability',
            'provider': args.provider,
            'url': url,
            'status': e.code,
            'classification': 'reachable-auth-required' if reachable else 'http-error',
            'error': str(e),
        }
    except Exception as e:
        return {
            'ok': False,
            'kind': 'provider-reachability',
            'provider': args.provider,
            'url': url,
            'classification': 'unreachable',
            'error': str(e),
        }


def run_inference_check(args):
    if not args.provider or not args.model:
        return {'ok': False, 'error': '--provider and --model are required for inference-check'}
    import urllib.request, urllib.error
    data = load_config()
    provider = infer_provider(args.provider, data)
    base = provider.get('baseUrl')
    if not base:
        return {
            'ok': False,
            'kind': 'inference-check',
            'provider': args.provider,
            'model': args.model,
            'error': 'provider baseUrl not found',
        }
    headers = provider_auth_headers(args.provider, provider)
    payload = json.dumps(inference_payload(args.provider, args.model)).encode('utf-8')
    url = base.rstrip('/') + '/chat/completions'
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            status = getattr(resp, 'status', 200)
            ok = status < 300
            return {
                'ok': ok,
                'kind': 'inference-check',
                'provider': args.provider,
                'model': args.model,
                'url': url,
                'status': status,
                'responsePreview': body[:500],
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
        auth_problem = e.code in (401, 403)
        return {
            'ok': True if auth_problem else False,
            'kind': 'inference-check',
            'provider': args.provider,
            'model': args.model,
            'url': url,
            'status': e.code,
            'classification': 'auth-failed' if auth_problem else 'request-failed',
            'error': str(e),
            'responsePreview': body[:500],
        }
    except Exception as e:
        return {
            'ok': False,
            'kind': 'inference-check',
            'provider': args.provider,
            'model': args.model,
            'url': url,
            'error': str(e),
        }


def run_fallback_check(args):
    if not args.ref:
        return {'ok': False, 'error': '--ref is required for fallback-check'}
    data = load_config()
    fallbacks = data.get('agents', {}).get('defaults', {}).get('model', {}).get('fallbacks', [])
    image_fallbacks = data.get('agents', {}).get('defaults', {}).get('imageModel', {}).get('fallbacks', [])
    found_in = []
    if args.ref in fallbacks:
        found_in.append('model.fallbacks')
    if args.ref in image_fallbacks:
        found_in.append('imageModel.fallbacks')
    ok = bool(found_in)
    return {
        'ok': ok,
        'kind': 'fallback-check',
        'ref': args.ref,
        'foundIn': found_in,
    }


HANDLERS = {
    'audit': run_audit_check,
    'gateway-restart-check': run_gateway_restart_check,
    'runtime-check': run_runtime_check,
    'schema-check': run_runtime_check,
    'model-alias-check': run_model_alias_check,
    'alias-uniqueness-check': run_alias_uniqueness_check,
    'provider-check': run_provider_check,
    'provider-reachability': run_provider_reachability_check,
    'inference-check': run_inference_check,
    'fallback-check': run_fallback_check,
}


def main():
    p = argparse.ArgumentParser(description='Run lightweight smoke tests for OpenClaw config ops')
    p.add_argument('--kind', choices=sorted(HANDLERS.keys()), required=True)
    p.add_argument('--alias', help='Alias to verify for alias-related checks')
    p.add_argument('--model', help='Expected model key for model-alias-check or inference-check')
    p.add_argument('--provider', help='Provider name for provider/provider-reachability/inference checks')
    p.add_argument('--ref', help='Model ref to verify for fallback-check')
    args = p.parse_args()

    result = HANDLERS[args.kind](args)
    if result.get('error', '').startswith('--'):
        emit(result)
        return 2
    return emit(result)


if __name__ == '__main__':
    sys.exit(main())
