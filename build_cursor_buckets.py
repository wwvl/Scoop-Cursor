import json
import os
import copy
from typing import Dict, Any, Tuple

TEMPLATE_OLD = 'bucket/template/cursor.template.bak'
TEMPLATE_NEW = 'bucket/template/cursor.template'
OUTPUT_DIR = 'bucket'
ARCH_MAP = {'x86': '32bit', 'x64': '64bit', 'arm64': 'arm64'}

def load_json(path: str) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        return None

def save_json(path: str, data: Any) -> None:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save {path}: {e}")

def process_arch_old(arch_data: Dict[str, Any]) -> Dict[str, str]:
    result = {}
    url = arch_data.get('url', '')
    if url and not url.endswith('#/dl.7z'):
        url += '#/dl.7z'
    result['url'] = url
    if 'sha512' in arch_data:
        result['hash'] = 'sha512:' + arch_data['sha512']
    elif 'sha256' in arch_data:
        result['hash'] = arch_data['sha256']
    else:
        result['hash'] = ''
    return result

def process_arch_new(arch_data: Dict[str, Any]) -> Dict[str, str]:
    result = {}
    result['url'] = arch_data.get('url', '')
    if 'sha512' in arch_data:
        result['hash'] = arch_data['sha512']
    elif 'sha256' in arch_data:
        result['hash'] = arch_data['sha256']
    else:
        result['hash'] = ''
    return result

def replace_template_vars(bucket: Dict[str, Any], version: str) -> None:
    for i, bin_item in enumerate(bucket.get('bin', [])):
        bucket['bin'][i][1] = bin_item[1].replace('{version}', version)
    for i, shortcut in enumerate(bucket.get('shortcuts', [])):
        bucket['shortcuts'][i][1] = shortcut[1].replace('{version}', version)

def parse_version(version: str) -> Tuple[int, int, int]:
    if version.startswith('0.3'):
        return (0, 3, int(version.split('.')[-1].lstrip('x')) if 'x' in version else 0)
    parts = version.split('.')
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))

def get_version_type(version: str) -> str:
    v = parse_version(version)
    if v < (0, 42, 0):
        return 'old_x64'  # 0.3x ~ 0.41
    elif v < (0, 45, 15):
        return 'old_multi'  # 0.42 ~ 0.45.14
    else:
        return 'new'  # 0.45.15 及以上

def collect_all_versions(data_dir: str) -> list:
    all_versions = []
    for fname in os.listdir(data_dir):
        if not fname.endswith('.json'):
            continue
        data_file = os.path.join(data_dir, fname)
        if not os.path.isfile(data_file):
            continue
        data = load_json(data_file)
        if not data:
            continue
        for version, version_data in data.items():
            all_versions.append({'version': version, 'version_data': version_data})
    return all_versions

def generate_bucket(version: str, version_data: dict) -> None:
    vtype = get_version_type(version)
    if vtype == 'old_x64':
        template_path = TEMPLATE_OLD
        archs = ['x64']
        process_arch_fn = process_arch_old
    elif vtype == 'old_multi':
        template_path = TEMPLATE_OLD
        archs = ['x86', 'x64', 'arm64']
        process_arch_fn = process_arch_old
    else:
        template_path = TEMPLATE_NEW
        archs = ['x64', 'arm64']
        process_arch_fn = process_arch_new
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load template: {e}")
        return
    bucket = copy.deepcopy(template)
    bucket['version'] = version
    bucket['architecture'] = {}
    for src_arch in archs:
        if src_arch in version_data:
            dst_arch = ARCH_MAP[src_arch]
            bucket['architecture'][dst_arch] = copy.deepcopy(template['architecture'][dst_arch])
            bucket['architecture'][dst_arch].update(
                process_arch_fn(version_data[src_arch])
            )
    replace_template_vars(bucket, version)
    out_path = os.path.join(OUTPUT_DIR, f'cursor-{version}.json')
    save_json(out_path, bucket)
    print(f'Generated: {out_path}')

def main():
    all_versions = collect_all_versions('data')
    for vinfo in all_versions:
        generate_bucket(vinfo['version'], vinfo['version_data'])

if __name__ == '__main__':
    main()
