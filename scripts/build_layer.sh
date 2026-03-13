#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

LAYER_DIR="$PROJECT_ROOT/lambdas/shared_layer/python"

echo "Cleaning $LAYER_DIR ..."
rm -rf "$LAYER_DIR"
mkdir -p "$LAYER_DIR"

echo "Copying lambdas/shared/*.py ..."
cp "$PROJECT_ROOT"/lambdas/shared/*.py "$LAYER_DIR/"

echo "Copying lambdas/email_renderer/templates.py ..."
cp "$PROJECT_ROOT/lambdas/email_renderer/templates.py" "$LAYER_DIR/"

echo "Done. Contents of $LAYER_DIR:"
ls -1 "$LAYER_DIR"
