#!/usr/bin/env python3
import os
import sys
import requests
from pathlib import Path
from zipfile import ZipFile

# ================== CONFIGURATION ==================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = "your-username"
REPO = "your-repo"
TAG_WORKFLOW_MAP = {"v1.22": "build-and-scan.yml"}
ARTIFACT_NAME = "security_scanning_image_tag"
# ===================================================

if not GITHUB_TOKEN:
    print("❌ ERROR: Set GITHUB_TOKEN environment variable!")
    sys.exit(1)

desktop = Path.home() / "Desktop"
output_dir = desktop / f"security_reports_{os.getpid()}"
output_dir.mkdir(exist_ok=True)
print(f"📁 Saving reports to: {output_dir}\n")

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
# ✅ FIXED: Removed space
base_url = f"https://api.github.com/repos/{OWNER}/{REPO}"

session = requests.Session()
session.headers.update(headers)

def get_commit_sha(tag):
    """Get commit SHA for a tag (handles both lightweight and annotated)"""
    url = f"{base_url}/git/ref/tags/{tag}"
    resp = session.get(url)
    if resp.status_code == 404:
        raise ValueError(f"Tag '{tag}' not found")
    resp.raise_for_status()
    
    tag_data = resp.json()
    # Handle annotated tags (point to tag object, not commit)
    if tag_data["object"]["type"] == "tag":
        tag_obj_resp = session.get(tag_data["object"]["url"])
        tag_obj_resp.raise_for_status()
        return tag_obj_resp.json()["object"]["sha"]
    return tag_data["object"]["sha"]

def get_latest_completed_run(workflow_file, sha):
    """Get latest completed workflow run for a specific commit"""
    url = f"{base_url}/actions/workflows/{workflow_file}/runs"
    params = {
        "head_sha": sha,
        "status": "completed",  # ✅ Any completed run (success/failure)
        "per_page": 1
    }
    resp = session.get(url, params=params)
    resp.raise_for_status()
    runs = resp.json()
    return runs["workflow_runs"][0]["id"] if runs["total_count"] > 0 else None

def get_artifact_id(run_id):
    """Find specific artifact ID in a run"""
    # ✅ Using name parameter is more efficient
    url = f"{base_url}/actions/runs/{run_id}/artifacts"
    resp = session.get(url, params={"name": ARTIFACT_NAME})
    resp.raise_for_status()
    artifacts = resp.json()["artifacts"]
    return artifacts[0]["id"] if artifacts else None

def download_and_extract_artifact(artifact_id, output_dir, tag):
    """Download and extract artifact ZIP"""
    url = f"{base_url}/actions/artifacts/{artifact_id}/zip"
    zip_path = output_dir / f"{tag}.zip"
    extract_path = output_dir / tag
    
    # Download with stream=True for large files
    with session.get(url, stream=True, headers={"Accept": "application/octet-stream"}) as r:
        if r.status_code == 410:
            raise Exception("Artifact expired (retention period exceeded)")
        r.raise_for_status()
        
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    
    # Extract
    extract_path.mkdir(exist_ok=True)
    with ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    
    print(f"  ✅ Saved and extracted: {tag}")
    return extract_path

# Main loop
for tag, workflow in TAG_WORKFLOW_MAP.items():
    print(f"🔍 Processing: tag='{tag}' | workflow='{workflow}'")
    try:
        # Verify workflow exists
        workflow_url = f"{base_url}/actions/workflows/{workflow}"
        if session.get(workflow_url).status_code == 404:
            print(f"  ❌ Workflow '{workflow}' not found at {workflow_url}")
            continue

        sha = get_commit_sha(tag)
        print(f"  → Commit: {sha[:8]}...")

        run_id = get_latest_completed_run(workflow, sha)
        if not run_id:
            print(f"  ❌ No completed run found for commit")
            continue

        artifact_id = get_artifact_id(run_id)
        if not artifact_id:
            print(f"  ❌ Artifact '{ARTIFACT_NAME}' not found")
            continue

        extract_path = download_and_extract_artifact(artifact_id, output_dir, tag)
        
        # Display content preview
        content_file = extract_path / ARTIFACT_NAME
        if content_file.exists():
            content = content_file.read_text().strip()
            print(f"  → Content: {content[:100]}{'...' if len(content) > 100 else ''}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

print(f"\n🎉 Done! Reports at:\n{output_dir}")
