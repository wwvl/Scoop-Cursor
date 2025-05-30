import os
import re
import json
import hashlib
import requests
import tempfile
from pathlib import Path

# Define paths for data and bucket directories, and template/metadata files
# These are relative to the script's parent directory

data_dir = Path(__file__).parent.parent / "data"
bucket_dir = Path(__file__).parent.parent / "bucket"
template_path = bucket_dir / "template" / "cursor.template"
latest_json_path = data_dir / "latest.json"

# API endpoint to fetch the latest version info
API_URL = "https://api2.cursor.sh/updates/api/update/win32-x64/cursor/0.0.0/"

# Download a file from the given URL and calculate its sha256 hash
# Returns the sha256 hex digest


def download_and_sha256(url):
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


# Query the API to get the latest version and build hash
# Returns (version, build_hash)
def get_latest_info():
    resp = requests.get(API_URL)
    resp.raise_for_status()
    data = resp.json()
    version = data["version"]
    url = data["url"]
    # Extract build hash from the download URL (after 'production/')
    m = re.search(r"production/([0-9a-f]{40})/", url)
    if not m:
        raise Exception("Failed to extract build hash from url")
    build = m.group(1)
    return version, build


# Get the major.minor part of a version string, e.g. '0.50.7' -> '0.50'
def get_major_minor(version):
    parts = version.split(".")
    return f"{parts[0]}.{parts[1]}"


# Update or create the data/{major.minor}.json file with the new version info
def update_data_json(version, build, x64_url, x64_sha, arm64_url, arm64_sha):
    major_minor = get_major_minor(version)
    data_json_path = data_dir / f"{major_minor}.json"
    if data_json_path.exists():
        with open(data_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    # Insert the new version
    new_entry = {
        "x64": {"url": x64_url, "sha256": x64_sha},
        "arm64": {"url": arm64_url, "sha256": arm64_sha},
    }
    data[version] = new_entry

    # Sort all versions in descending order
    def parse_version(v):
        return [int(x) for x in v.split(".")]

    sorted_items = sorted(
        data.items(), key=lambda item: parse_version(item[0]), reverse=True
    )
    sorted_data = {k: v for k, v in sorted_items}
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)
    print(f"Updated {data_json_path}")


# Update the data/latest.json file with the latest version and build info
def update_latest_json(version, build, x64_url, x64_sha, arm64_url, arm64_sha):
    latest = {
        "version": version,
        "build": build,
        "releases": {
            "x64": {"url": x64_url, "sha256": x64_sha},
            "arm64": {"url": arm64_url, "sha256": arm64_sha},
        },
    }
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, indent=4, ensure_ascii=False)
    print(f"Updated {latest_json_path}")


# Generate a new bucket/cursor-{version}.json file from the template
def update_bucket(version, build, x64_url, x64_sha, arm64_url, arm64_sha):
    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)
    # Fill in version and download info
    template["version"] = version
    template["architecture"]["64bit"]["url"] = x64_url
    template["architecture"]["64bit"]["hash"] = x64_sha
    template["architecture"]["arm64"]["url"] = arm64_url
    template["architecture"]["arm64"]["hash"] = arm64_sha
    # Update bin and shortcuts fields with the new version
    for i, item in enumerate(template["bin"]):
        if isinstance(item, list) and len(item) > 1:
            template["bin"][i][1] = f"cursor_{version}"
    for i, item in enumerate(template["shortcuts"]):
        if isinstance(item, list) and len(item) > 1:
            template["shortcuts"][i][1] = f"Cursor {version}"
    out_path = bucket_dir / f"cursor-{version}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=4, ensure_ascii=False)
    print(f"Generated {out_path}")


# Compare two version strings (e.g. 0.50.7 <= 0.50.8)
# Returns True if v1 <= v2
def version_leq(v1, v2):
    """Return True if v1 <= v2, where v1/v2 are like '0.50.7'"""

    def parse(v):
        return [int(x) for x in v.split(".")]

    return parse(v1) <= parse(v2)


# Main workflow: check for updates, download, update data and bucket
def main():
    # 1. Get latest version and build hash from API
    version, build = get_latest_info()
    print(f"Latest version: {version}, build: {build}")

    # 2. Compare with local latest.json
    if latest_json_path.exists():
        with open(latest_json_path, "r", encoding="utf-8") as f:
            latest = json.load(f)
        latest_version = latest.get("version")
        if version_leq(version, latest_version):
            print(
                f"Already up-to-date or local version is newer (local: {latest_version}, remote: {version}), no update needed."
            )
            return

    # 3. Download installers and calculate sha256
    x64_url = f"https://downloads.cursor.com/production/{build}/win32/x64/user-setup/CursorUserSetup-x64-{version}.exe"
    arm64_url = f"https://downloads.cursor.com/production/{build}/win32/arm64/user-setup/CursorUserSetup-arm64-{version}.exe"
    print("Downloading x64...")
    x64_sha = download_and_sha256(x64_url)
    print("Downloading arm64...")
    arm64_sha = download_and_sha256(arm64_url)

    # 4. Update data files
    update_data_json(version, build, x64_url, x64_sha, arm64_url, arm64_sha)
    update_latest_json(version, build, x64_url, x64_sha, arm64_url, arm64_sha)

    # 5. Update bucket file
    update_bucket(version, build, x64_url, x64_sha, arm64_url, arm64_sha)
    print("All done.")


if __name__ == "__main__":
    main()
