import os
import json
import hashlib
import requests
import tempfile
from pathlib import Path
import subprocess

# 配置路径
bucket_dir = Path(__file__).parent.parent / "bucket"
template_path = bucket_dir / "template" / "cursor.template"
cursor_json_path = bucket_dir / "cursor.json"

# 远程 API
API_URL = "https://www.cursor.com/api/download?platform=win32-x64-user&releaseTrack=latest"

def download_and_sha256(url):
    """
    下载文件并计算 sha256
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

def version_gt(v1, v2):
    """
    判断 v1 > v2
    """
    def parse(v):
        return [int(x) for x in v.split(".")]
    return parse(v1) > parse(v2)

def update_bucket(version, x64_url, x64_sha, arm64_url, arm64_sha):
    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)
    template["version"] = version
    template["architecture"]["64bit"]["url"] = x64_url
    template["architecture"]["64bit"]["hash"] = x64_sha
    template["architecture"]["arm64"]["url"] = arm64_url
    template["architecture"]["arm64"]["hash"] = arm64_sha
    for i, item in enumerate(template["bin"]):
        if isinstance(item, list) and len(item) > 1:
            template["bin"][i][1] = f"cursor_{version}"
    for i, item in enumerate(template["shortcuts"]):
        if isinstance(item, list) and len(item) > 1:
            template["shortcuts"][i][1] = f"Cursor {version}"
    out_path = bucket_dir / f"cursor-{version}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=4, ensure_ascii=False)
        f.write("\n")
    print(f"Generated {out_path}")

def update_cursor_json(version, x64_url, x64_sha, arm64_url, arm64_sha):
    with open(cursor_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = version
    data["architecture"]["64bit"]["url"] = x64_url
    data["architecture"]["64bit"]["hash"] = x64_sha
    data["architecture"]["arm64"]["url"] = arm64_url
    data["architecture"]["arm64"]["hash"] = arm64_sha
    with open(cursor_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    print(f"Updated {cursor_json_path}")

def main():
    # 1. 获取远程 JSON
    resp = requests.get(API_URL)
    resp.raise_for_status()
    remote = resp.json()
    version = remote["version"]
    commitSha = remote["commitSha"]
    print(f"Remote version: {version}, commitSha: {commitSha}")

    # # 2. 获取本地 version
    # with open(cursor_json_path, "r", encoding="utf-8") as f:
    #     local = json.load(f)
    # local_version = local["version"]
    # print(f"Local version: {local_version}")

    # # 3. 比较版本
    # if not version_gt(version, local_version):
    #     print(f"Already up-to-date or local version is newer (local: {local_version}, remote: {version}), no update needed.")
    #     return

    # 4. 下载并计算 sha256
    x64_url = f"https://downloads.cursor.com/production/{commitSha}/win32/x64/user-setup/CursorUserSetup-x64-{version}.exe"
    arm64_url = f"https://downloads.cursor.com/production/{commitSha}/win32/arm64/user-setup/CursorUserSetup-arm64-{version}.exe"
    print("Downloading x64...")
    x64_sha = download_and_sha256(x64_url)
    print("Downloading arm64...")
    arm64_sha = download_and_sha256(arm64_url)

    # 5. 生成新 bucket/cursor-{version}.json
    update_bucket(version, x64_url, x64_sha, arm64_url, arm64_sha)
    # 6. 更新 bucket/cursor.json
    update_cursor_json(version, x64_url, x64_sha, arm64_url, arm64_sha)

    # # 7. git add/commit/push
    # try:
    #     subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    #     subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    #     subprocess.run(["git", "add", "."], check=True)
    #     subprocess.run(["git", "commit", "-m", f"chore: add cursor {version}.{commitSha}"], check=True)
    #     # 这里 GITHUB_REF 需在 CI 环境变量中，手动运行可注释掉 push
    #     github_ref = os.environ.get("GITHUB_REF")
    #     if github_ref:
    #         branch = github_ref.replace("refs/heads/", "")
    #         subprocess.run(["git", "push", "origin", branch], check=True)
    #     else:
    #         print("[Warn] GITHUB_REF not set, skip git push.")
    # except Exception as e:
    #     print(f"[Warn] git commit/push failed: {e}")

if __name__ == "__main__":
    main()
