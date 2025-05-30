import json
import os
import copy
from typing import Dict, Any, Tuple
from pathlib import Path

# Set base directory as the parent of the scripts directory
base_dir = Path(__file__).parent.parent
TEMPLATE_OLD = str(base_dir / "bucket" / "template" / "cursor.template.bak")
TEMPLATE_NEW = str(base_dir / "bucket" / "template" / "cursor.template")
OUTPUT_DIR = str(base_dir / "bucket")
DATA_PATH = str(base_dir / "data")  # Data directory path
ARCH_MAP = {"x86": "32bit", "x64": "64bit", "arm64": "arm64"}


def load_json(path: str) -> Any:
    """
    Load a JSON file and return its content as a Python object.
    加载 JSON 文件并返回其内容为 Python 对象。

    Args:
        path (str): Path to the JSON file.
    Returns:
        Any: The loaded Python object.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        return None


def save_json(path: str, data: Any) -> None:
    """
    Save a Python object as a JSON file.
    将 Python 对象保存为 JSON 文件。

    Args:
        path (str): Path to save the JSON file.
        data (Any): The Python object to save.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save {path}: {e}")


def process_arch_old(arch_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Process architecture data for old template format.
    处理旧模板格式的架构数据。

    Args:
        arch_data (dict): Architecture data.
    Returns:
        dict: Processed architecture data.
    """
    result = {}
    url = arch_data.get("url", "")
    # For old format, append #/dl.7z if not present
    # 对于旧格式，如果没有以 #/dl.7z 结尾则追加
    if url and not url.endswith("#/dl.7z"):
        url += "#/dl.7z"
    result["url"] = url
    # Prefer sha512, fallback to sha256
    # 优先使用 sha512，没有则用 sha256
    if "sha512" in arch_data:
        result["hash"] = "sha512:" + arch_data["sha512"]
    elif "sha256" in arch_data:
        result["hash"] = arch_data["sha256"]
    else:
        result["hash"] = ""
    return result


def process_arch_new(arch_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Process architecture data for new template format.
    处理新模板格式的架构数据。

    Args:
        arch_data (dict): Architecture data.
    Returns:
        dict: Processed architecture data.
    """
    result = {}
    result["url"] = arch_data.get("url", "")
    # Prefer sha512, fallback to sha256
    # 优先使用 sha512，没有则用 sha256
    if "sha512" in arch_data:
        result["hash"] = arch_data["sha512"]
    elif "sha256" in arch_data:
        result["hash"] = arch_data["sha256"]
    else:
        result["hash"] = ""
    return result


def replace_template_vars(bucket: Dict[str, Any], version: str) -> None:
    """
    Replace {version} placeholders in bin and shortcuts fields.
    替换 bin 和 shortcuts 字段中的 {version} 占位符。

    Args:
        bucket (dict): The bucket dictionary.
        version (str): The version string.
    """
    for i, bin_item in enumerate(bucket.get("bin", [])):
        bucket["bin"][i][1] = bin_item[1].replace("{version}", version)
    for i, shortcut in enumerate(bucket.get("shortcuts", [])):
        bucket["shortcuts"][i][1] = shortcut[1].replace("{version}", version)


def parse_version(version: str) -> Tuple[int, int, int]:
    """
    Parse version string into a tuple of integers for comparison/sorting.
    将版本字符串解析为整数元组以便比较/排序。

    Args:
        version (str): Version string.
    Returns:
        tuple: Parsed version as a tuple of integers.
    """
    if version.startswith("0.3"):
        return (0, 3, int(version.split(".")[-1].lstrip("x")) if "x" in version else 0)
    parts = version.split(".")
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def get_version_type(version: str) -> str:
    """
    Determine which template type to use based on version number.
    根据版本号判断使用哪种模板类型。

    Args:
        version (str): Version string.
    Returns:
        str: Template type.
    """
    v = parse_version(version)
    if v < (0, 42, 0):
        return "old_x64"  # 0.3x ~ 0.41
    elif v < (0, 45, 15):
        return "old_multi"  # 0.42 ~ 0.45.14
    else:
        return "new"  # 0.45.15 及以上


def collect_all_versions(data_dir: str) -> list:
    """
    Collect all version entries from data directory, skipping latest.json.
    收集 data 目录下所有版本条目，跳过 latest.json。

    Args:
        data_dir (str): Data directory path.
    Returns:
        list: All version entries.
    """
    all_versions = []
    for fname in os.listdir(data_dir):
        if not fname.endswith(".json"):
            continue
        if fname == "latest.json":
            continue  # skip latest.json
        data_file = os.path.join(data_dir, fname)
        if not os.path.isfile(data_file):
            continue
        data = load_json(data_file)
        if not data:
            continue
        for version, version_data in data.items():
            all_versions.append({"version": version, "version_data": version_data})
    return all_versions


def generate_bucket(version: str, version_data: dict) -> None:
    """
    Generate a bucket file for a specific version using the appropriate template.
    使用合适的模板为指定版本生成 bucket 文件。

    Args:
        version (str): Version string.
        version_data (dict): Version data.
    """
    vtype = get_version_type(version)
    if vtype == "old_x64":
        template_path = TEMPLATE_OLD
        archs = ["x64"]
        process_arch_fn = process_arch_old
    elif vtype == "old_multi":
        template_path = TEMPLATE_OLD
        archs = ["x86", "x64", "arm64"]
        process_arch_fn = process_arch_old
    else:
        template_path = TEMPLATE_NEW
        archs = ["x64", "arm64"]
        process_arch_fn = process_arch_new
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load template: {e}")
        return
    bucket = copy.deepcopy(template)
    bucket["version"] = version
    bucket["architecture"] = {}
    # Fill architecture info for each supported arch
    for src_arch in archs:
        if src_arch in version_data:
            dst_arch = ARCH_MAP[src_arch]
            bucket["architecture"][dst_arch] = copy.deepcopy(
                template["architecture"][dst_arch]
            )
            bucket["architecture"][dst_arch].update(
                process_arch_fn(version_data[src_arch])
            )
    # Replace {version} in bin and shortcuts
    replace_template_vars(bucket, version)
    out_path = os.path.join(OUTPUT_DIR, f"cursor-{version}.json")
    save_json(out_path, bucket)
    print(f"Generated: {out_path}")


def main():
    """
    Main entry: collect all versions and generate bucket files for each.
    主入口：收集所有版本并为每个版本生成 bucket 文件。
    """
    all_versions = collect_all_versions(DATA_PATH)
    for vinfo in all_versions:
        generate_bucket(vinfo["version"], vinfo["version_data"])


if __name__ == "__main__":
    main()
