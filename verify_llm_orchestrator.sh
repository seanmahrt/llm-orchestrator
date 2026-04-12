#!/bin/bash

set -e

BASE="custom_components/llm_orchestrator"
OLD_FOLDER="$BASE/conversation"
NEW_FOLDER="$BASE/conversation_agent"
PLATFORM_FILE="$BASE/conversation.py"

echo "============================================================"
echo " LLM ORCHESTRATOR AUTO-FIX SCRIPT"
echo "============================================================"
echo

# 1. Verify integration folder
if [ ! -d "$BASE" ]; then
    echo "❌ ERROR: Integration folder not found: $BASE"
    exit 1
fi
echo "✔ Integration folder found"

# 2. Verify platform file
if [ ! -f "$PLATFORM_FILE" ]; then
    echo "❌ ERROR: conversation.py not found"
    exit 1
fi
echo "✔ conversation.py found"

# 3. Detect folder/file conflict
if [ -d "$OLD_FOLDER" ]; then
    echo "⚠ Detected folder named 'conversation/' — this conflicts with conversation.py"
    echo "→ Renaming folder to 'conversation_agent/'"

    # Remove old target if exists
    if [ -d "$NEW_FOLDER" ]; then
        echo "⚠ Removing old conversation_agent folder"
        rm -rf "$NEW_FOLDER"
    fi

    mv "$OLD_FOLDER" "$NEW_FOLDER"
    echo "✔ Renamed: conversation/ → conversation_agent/"
else
    echo "✔ No conflicting folder named 'conversation/'"
fi

# 4. Update import path inside conversation.py
echo "Updating import path inside conversation.py..."

sed -i \
    "s|from custom_components.llm_orchestrator.conversation.agent|from custom_components.llm_orchestrator.conversation_agent.agent|" \
    "$PLATFORM_FILE"

echo "✔ Updated import path"

# 5. Clean stale caches
echo "Cleaning stale Python caches..."

find "$BASE" -name "__pycache__" -type d -exec rm -rf {} +
find "$BASE" -name "*.pyc" -delete
find "$BASE" -name "*.pyo" -delete

echo "✔ Cache cleaned"

# 6. Verify new structure
echo
echo "============================================================"
echo " FINAL STRUCTURE:"
echo "============================================================"
tree "$BASE"

echo
echo "============================================================"
echo " DONE."
echo "============================================================"
echo "Now copy the updated folder into Home Assistant:"
echo "  /config/custom_components/llm_orchestrator/"
echo
echo "Then restart Home Assistant and check logs for:"
echo "  LLM Orchestrator conversation agent registered"
echo
