#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
CHANGE_LOG = SKILL_DIR / 'references' / 'change-log.jsonl'


def run(cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def timestamp():
    return dt.datetime.now().strftime('%Y%m%d-%H%M%S')


def backup_file(path: Path):
    backup = path.parent / f"{path.name}.backup-{timestamp()}"
    shutil.copy2(path, backup)
    return backup


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


def parse_path(dotted_path: str):
    import re
    pattern = r'\["([^"]+)"\]|\[\'([^\']+)\'\]|([^.\[]+)'
    matches = re.findall(pattern, dotted_path)
    parts = []
    for m in matches:
        key = m[0] or m[1] or m[2]
        if key:
            parts.append(key)
    return parts


def apply_set(data, dotted_path, raw_value):
    value = json.loads(raw_value)
    parts = parse_path(dotted_path)
    cur = data
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value
    return data


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def append_log(entry):
    CHANGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANGE_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


def restart_openclaw(note):
    proc = run(['openclaw', 'gateway', 'restart'], check=False)
    return {
        'ok': proc.returncode == 0,
        'code': proc.returncode,
        'stdout': proc.stdout.strip(),
        'stderr': proc.stderr.strip(),
        'note': note,
    }


def gateway_status():
    proc = run(['openclaw', 'gateway', 'status'], check=False)
    return {
        'ok': proc.returncode == 0,
        'code': proc.returncode,
        'stdout': proc.stdout.strip(),
        'stderr': proc.stderr.strip(),
    }


def main():
    p = argparse.ArgumentParser(description='Guarded OpenClaw config change runner')
    p.add_argument('--target', default=str(CONFIG_PATH))
    p.add_argument('--set', dest='set_ops', action='append', default=[], help='Set dotted.path to JSON value via dotted.path=<json>')
    p.add_argument('--reason', required=True)
    p.add_argument('--smoke-test', required=True, dest='smoke_test')
    p.add_argument('--restart', action='store_true')
    p.add_argument('--smoke-kind', choices=['audit', 'gateway-restart-check', 'runtime-check', 'schema-check'])
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    target = Path(args.target).expanduser()
    if not target.exists():
        print(json.dumps({'ok': False, 'error': f'missing target: {target}'}))
        return 1

    backup = backup_file(target)
    before_ok, before_err = validate_json(target)
    if not before_ok:
        print(json.dumps({'ok': False, 'error': 'target is not valid JSON before change', 'detail': before_err, 'backup': str(backup)}))
        return 2

    data = load_json(target)
    applied = []
    for op in args.set_ops:
        if '=' not in op:
            print(json.dumps({'ok': False, 'error': f'invalid --set op: {op}', 'backup': str(backup)}))
            return 3
        dotted, raw = op.split('=', 1)
        data = apply_set(data, dotted, raw)
        applied.append({'path': dotted, 'value': raw})

    if not args.dry_run:
        save_json(target, data)

    after_ok, after_err = validate_json(target)
    if not after_ok:
        shutil.copy2(backup, target)
        print(json.dumps({'ok': False, 'error': 'resulting JSON invalid; rolled back', 'detail': after_err, 'backup': str(backup)}))
        return 4

    semantic_result = None
    if not args.dry_run:
        semantic_result = semantic_validate()
        if not semantic_result['ok']:
            shutil.copy2(backup, target)
            print(json.dumps({'ok': False, 'error': 'semantic config validation failed; rolled back', 'backup': str(backup), 'semantic': semantic_result}, indent=2))
            return 5

    restart_result = None
    gateway_check = None
    smoke_result = None
    if args.restart and not args.dry_run:
        restart_result = restart_openclaw(args.reason)
        gateway_check = gateway_status()

    if args.smoke_kind and not args.dry_run:
        proc = run([
            str(SCRIPT_DIR / 'smoke_test.py'),
            '--kind',
            args.smoke_kind,
        ], check=False)
        smoke_result = {
            'ok': proc.returncode == 0,
            'kind': args.smoke_kind,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
        }

    entry = {
        'timestamp': dt.datetime.now().isoformat(),
        'target': str(target),
        'backup': str(backup),
        'reason': args.reason,
        'smokeTest': args.smoke_test,
        'applied': applied,
        'semantic': semantic_result,
        'restart': restart_result,
        'gatewayCheck': gateway_check,
        'smokeResult': smoke_result,
        'dryRun': args.dry_run,
    }
    append_log(entry)

    result = {
        'ok': True,
        'target': str(target),
        'backup': str(backup),
        'applied': applied,
        'semantic': semantic_result,
        'smokeTest': args.smoke_test,
        'restart': restart_result,
        'gatewayCheck': gateway_check,
        'smokeResult': smoke_result,
        'changeLog': str(CHANGE_LOG),
        'next': 'review smoke result and roll back if needed',
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
