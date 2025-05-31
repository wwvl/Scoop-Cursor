import sys
import os
import json
from pathlib import Path
import requests
import hashlib
import tempfile


def download_and_sha256(url):
    """
    Download a file from the given URL and calculate its sha256 hash.
    """
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
            temp_path = f.name
    sha256 = hashlib.sha256()
    with open(temp_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    os.remove(temp_path)
    return sha256.hexdigest()


def main():
    if len(sys.argv) < 2:
        print("update_sha256.py {major.minor} [version1 version2 ...]")
        sys.exit(1)
    major_minor = sys.argv[1]
    versions = sys.argv[2:] if len(sys.argv) > 2 else None

    data_dir = Path(__file__).parent.parent / "data"
    json_path = data_dir / f"{major_minor}.json"
    if not json_path.exists():
        print(f"文件不存在：{json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 需要处理的版本
    if versions:
        to_update = [v for v in versions if v in data]
        missing = [v for v in versions if v not in data]
        if missing:
            print(f"警告：以下版本在 {json_path} 中未找到：{', '.join(missing)}")
    else:
        to_update = list(data.keys())

    if not to_update:
        print("没有需要更新的版本")
        sys.exit(0)

    for version in to_update:
        print(f"处理版本：{version}")
        for arch in ["x64", "arm64"]:
            url = data[version][arch]["url"]
            print(f"  下载 {arch}: {url}")
            try:
                sha256 = download_and_sha256(url)
                print(f"  计算得到 sha256: {sha256}")
                data[version][arch]["sha256"] = sha256
            except Exception as e:
                print(f"  下载或计算失败：{e}")

    # 写回 json 文件
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    print(f"已更新：{json_path}")


if __name__ == "__main__":
    main()
