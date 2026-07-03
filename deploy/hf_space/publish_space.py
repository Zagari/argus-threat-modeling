#!/usr/bin/env python3
"""Publish the ARGUS & Cíclope demo to Hugging Face Spaces (Gradio SDK).

Mirrors `training/publish_hf.py`. A Space is just a Hub git repo, so publishing works
exactly like pushing a model. Requires a write token: `huggingface-cli login` (recommended
— the token stays in the local cache, never in this script) or the `HF_TOKEN` env var.

It (1) assembles the Space folder via build.sh and (2) creates/updates the Space and uploads it.

Usage:
  python deploy/hf_space/publish_space.py --repo zagari/argus-threat-modeling
  python deploy/hf_space/publish_space.py --repo zagari/argus-threat-modeling --private
  python deploy/hf_space/publish_space.py --repo x/y --dry-run   # assemble only, no upload
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="Space id, e.g. zagari/argus-threat-modeling")
    ap.add_argument("--private", action="store_true", help="create the Space as private")
    ap.add_argument("--build-dir", default=str(HERE / "_build"))
    ap.add_argument("--dry-run", action="store_true", help="only assemble the folder; do not upload")
    args = ap.parse_args()

    # 1) assemble the self-contained Space folder
    subprocess.run(["bash", str(HERE / "build.sh"), args.build_dir], check=True)
    if args.dry_run:
        print(f"[dry-run] assembled at {args.build_dir}; skipping upload.")
        return

    # 2) create/update the Space and upload
    try:
        from huggingface_hub import HfApi, whoami
    except ImportError:
        sys.exit("huggingface_hub não instalado — `pip install huggingface_hub`.")

    who = whoami().get("name")
    print(f"authenticated as: {who}")
    api = HfApi()
    api.create_repo(args.repo, repo_type="space", space_sdk="gradio",
                    private=args.private, exist_ok=True)
    api.upload_folder(folder_path=args.build_dir, repo_id=args.repo, repo_type="space",
                      commit_message="Deploy ARGUS & Cíclope demo (bring-your-own-key)")
    print(f"✓ published: https://huggingface.co/spaces/{args.repo}")


if __name__ == "__main__":
    main()
