#!/bin/sh
set -e

MODELS_FILE="${MODELS_FILE:-/models.yaml}"

if [ ! -f "$MODELS_FILE" ]; then
    echo "No models file at $MODELS_FILE, skipping."
    exit 0
fi

grep -E '^\s*-\s*\S' "$MODELS_FILE" | sed -E 's/^\s*-\s*//' | while read -r model; do
    [ -z "$model" ] && continue
    echo "==> ollama pull $model"
    ollama pull "$model"
done
