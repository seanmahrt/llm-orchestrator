#!/bin/bash

echo "============================================================"
echo " LLM ORCHESTRATOR INTEGRATION VERIFICATION SCRIPT"
echo "============================================================"
echo

BASE="custom_components/llm_orchestrator"

# Helper function
check() {
    if eval "$1"; then
        echo -e "✔ PASS: $2"
    else
        echo -e "✘ FAIL: $2"
    fi
}

echo "Checking directory structure..."
check "[ -d $BASE ]" "Integration folder exists: $BASE"
check "[ -f $BASE/manifest.json ]" "manifest.json exists"
check "[ -f $BASE/__init__.py ]" "__init__.py exists"
check "[ -f $BASE/conversation.py ]" "conversation.py exists"
check "[ -d $BASE/conversation ]" "conversation/ folder exists"
check "[ -f $BASE/conversation/agent.py ]" "conversation/agent.py exists"
check "[ -f $BASE/conversation/__init__.py ]" "conversation/__init__.py exists"

echo
echo "Checking for stale or problematic files..."
check "[ ! -d $BASE/__pycache__ ]" "No __pycache__ folder (good)"
check "[ ! -f $BASE/conversation.pyc ]" "No conversation.pyc"
check "[ ! -f $BASE/conversation.pyo ]" "No conversation.pyo"
check "[ ! -f $BASE/conversation.py.txt ]" "No hidden extension conversation.py.txt"
check "[ ! -f $BASE/conversation.py.disabled ]" "No disabled conversation.py file"

echo
echo "Checking manifest.json content..."
grep -q '"conversation": 

\["conversation"\]

' $BASE/manifest.json
check "[ \$? -eq 0 ]" "manifest.json declares conversation platform correctly"

echo
echo "Checking import path inside conversation.py..."
grep -q "custom_components.llm_orchestrator.conversation.agent" $BASE/conversation.py
check "[ \$? -eq 0 ]" "conversation.py uses absolute import for agent"

echo
echo "Checking for CRLF or BOM issues..."
if file $BASE/conversation.py | grep -q "CRLF"; then
    echo "✘ FAIL: conversation.py contains CRLF line endings"
else
    echo "✔ PASS: conversation.py uses correct LF line endings"
fi

if file $BASE/conversation.py | grep -q "UTF-8 Unicode (with BOM)"; then
    echo "✘ FAIL: conversation.py contains BOM"
else
    echo "✔ PASS: conversation.py has no BOM"
fi

echo
echo "============================================================"
echo " Verification complete."
echo "============================================================"
