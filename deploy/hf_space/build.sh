#!/usr/bin/env bash
# Assemble a self-contained Hugging Face Space folder for the ARGUS & Cíclope demo.
# The Space needs the Gradio entry + the backend package + the taxonomy YAML.
#
# Usage:  deploy/hf_space/build.sh [TARGET_DIR]      (default: deploy/hf_space/_build)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"                 # repo root (argus/)
DEST="${1:-$HERE/_build}"

rm -rf "$DEST"
mkdir -p "$DEST/backend" "$DEST/training/taxonomy"

# 1) Gradio entry + deps + Space card (README carries the Space frontmatter)
/bin/cp -f "$HERE/app.py" "$HERE/requirements.txt" "$HERE/README.md" "$DEST/"

# 2) Backend package (runtime code + knowledge catalogs); drop caches/tests
rsync -a --prune-empty-dirs \
  --exclude '__pycache__' --exclude '*.pyc' --exclude 'tests' \
  "$ROOT/backend/app" "$DEST/backend/"

# 3) Taxonomy YAML — powers the E2 label→class map
/bin/cp -f "$ROOT/training/taxonomy/mapeamento.yaml" "$DEST/training/taxonomy/"

echo "✓ Space assembled at: $DEST"
du -sh "$DEST"
echo "top-level:"; ls -1 "$DEST"
