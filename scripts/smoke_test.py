#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


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


def main():
    p = argparse.ArgumentParser(description='Run lightweight smoke tests for OpenClaw config ops')
    p.add_argument('--kind', choices=['audit', 'gateway-restart-check', 'model-alias-check', 'provider-check', 'fallback-check', 'schema-check', 'provider-reachability', 'inference-check'], required=True)
    p.add_argument('--alias', help='Alias to verify for model-alias-check')
    p.add_argument('--model', help='Expected model key for model-alias-check or inference-check')
    p.add_argument('--provider', help='Provider name for provider/provider-reachability/inference checks')
    p.add_argument('--ref', help='Model ref to verify for fallback-check')
    args = p.parse_args()

    if args.kind == 'audit':
        proc = run([str(SCRIPT_DIR / 'audit_openclaw_config.py')])
        print(json.dumps({'ok': proc.returncode == 0, 'kind': 'audit', 'stdout': proc.stdout, 'stderr': proc.stderr}, indent=2))
        return 0 if proc.returncode == 0 else 1

    if args.kind == 'gateway-restart-check':
        proc = run(['openclaw', 'gateway', 'status'])
        print(json.dumps({'ok': proc.returncode == 0, 'kind': 'gateway-restart-check', 'stdout': proc.stdout, 'stderr': proc.stderr}, indent=2))
        return 0 if proc.returncode == 0 else 1

    if args.kind == 'model-alias-check':
        if not args.alias or not args.model:
            print(json.dumps({'ok': False, 'error': '--alias and --model are required for model-alias-check'}, indent=2))
            return 2
        import pathlib
        cfg = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
        data = json.loads(cfg.read_text())
        models = data.get('agents', {}).get('defaults', {}).get('models', {})
        found = [k for k, v in models.items() if isinstance(v, dict) and v.get('alias') == args.alias]
        ok = args.model in found
        print(json.dumps({'ok': ok, 'kind': 'model-alias-check', 'alias': args.alias, 'expected': args.model, 'found': found}, indent=2))
        return 0 if ok else 1

    if args.kind == 'provider-check':
        if not args.provider:
            print(json.dumps({'ok': False, 'error': '--provider is required for provider-check'}, indent=2))
            return 2
        import pathlib
        cfg = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
        data = json.loads(cfg.read_text())
        providers = data.get('models', {}).get('providers', {})
        provider = providers.get(args.provider)
        ok = provider is not None and bool(provider.get('models'))
        print(json.dumps({'ok': ok, 'kind': 'provider-check', 'provider': args.provider, 'hasProvider': provider is not None, 'modelCount': len(provider.get('models', [])) if provider else 0}, indent=2))
        return 0 if ok else 1

    if args.kind == 'schema-check':
        proc = run(['openclaw', 'gateway', 'status'])
        ok = proc.returncode == 0
        print(json.dumps({'ok': ok, 'kind': 'schema-check', 'stdout': proc.stdout, 'stderr': proc.stderr}, indent=2))
        return 0 if ok else 1

    if args.kind == 'provider-reachability':
        if not args.provider:
            print(json.dumps({'ok': False, 'error': '--provider is required for provider-reachability'}, indent=2))
            return 2
        import pathlib
        import urllib.request, urllib.error
        cfg = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
        data = json.loads(cfg.read_text())
        base = infer_api_base(args.provider, data)
        if not base:
            print(json.dumps({'ok': False, 'kind': 'provider-reachability', 'provider': args.provider, 'error': 'provider baseUrl not found'}, indent=2))
            return 1
        try:
            req = urllib.request.Request(base.rstrip('/') + '/models', headers={'User-Agent': 'openclaw-config-ops-smoke'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = getattr(resp, 'status', 200)
                ok = status < 500
                print(json.dumps({'ok': ok, 'kind': 'provider-reachability', 'provider': args.provider, 'url': base.rstrip('/') + '/models', 'status': status, 'classification': 'reachable'}, indent=2))
                return 0 if ok else 1
        except urllib.error.HTTPError as e:
            reachable = e.code in (401, 403)
            print(json.dumps({'ok': reachable, 'kind': 'provider-reachability', 'provider': args.provider, 'url': base.rstrip('/') + '/models', 'status': e.code, 'classification': 'reachable-auth-required' if reachable else 'http-error', 'error': str(e)}, indent=2))
            return 0 if reachable else 1
        except Exception as e:
            print(json.dumps({'ok': False, 'kind': 'provider-reachability', 'provider': args.provider, 'url': base.rstrip('/') + '/models', 'classification': 'unreachable', 'error': str(e)}, indent=2))
            return 1

    if args.kind == 'inference-check':
        if not args.provider or not args.model:
            print(json.dumps({'ok': False, 'error': '--provider and --model are required for inference-check'}, indent=2))
            return 2
        import pathlib
        import urllib.request, urllib.error
        cfg = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
        data = json.loads(cfg.read_text())
        provider = infer_provider(args.provider, data)
        base = provider.get('baseUrl')
        if not base:
            print(json.dumps({'ok': False, 'kind': 'inference-check', 'provider': args.provider, 'model': args.model, 'error': 'provider baseUrl not found'}, indent=2))
            return 1
        headers = provider_auth_headers(args.provider, provider)
        payload = json.dumps(inference_payload(args.provider, args.model)).encode('utf-8')
        url = base.rstrip('/') + '/chat/completions'
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode('utf-8', errors='replace')
                status = getattr(resp, 'status', 200)
                ok = status < 300
                print(json.dumps({'ok': ok, 'kind': 'inference-check', 'provider': args.provider, 'model': args.model, 'url': url, 'status': status, 'responsePreview': body[:500]}, indent=2))
                return 0 if ok else 1
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
            auth_problem = e.code in (401, 403)
            print(json.dumps({'ok': False if not auth_problem else True, 'kind': 'inference-check', 'provider': args.provider, 'model': args.model, 'url': url, 'status': e.code, 'classification': 'auth-failed' if auth_problem else 'request-failed', 'error': str(e), 'responsePreview': body[:500]}, indent=2))
            return 0 if auth_problem else 1
        except Exception as e:
            print(json.dumps({'ok': False, 'kind': 'inference-check', 'provider': args.provider, 'model': args.model, 'url': url, 'error': str(e)}, indent=2))
            return 1

    if args.kind == 'fallback-check':
        if not args.ref:
            print(json.dumps({'ok': False, 'error': '--ref is required for fallback-check'}, indent=2))
            return 2
        import pathlib
        cfg = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
        data = json.loads(cfg.read_text())
        fallbacks = data.get('agents', {}).get('defaults', {}).get('model', {}).get('fallbacks', [])
        image_fallbacks = data.get('agents', {}).get('defaults', {}).get('imageModel', {}).get('fallbacks', [])
        found_in = []
        if args.ref in fallbacks:
            found_in.append('model.fallbacks')
        if args.ref in image_fallbacks:
            found_in.append('imageModel.fallbacks')
        ok = bool(found_in)
        print(json.dumps({'ok': ok, 'kind': 'fallback-check', 'ref': args.ref, 'foundIn': found_in}, indent=2))
        return 0 if ok else 1

    return 1


if __name__ == '__main__':
    sys.exit(main())
