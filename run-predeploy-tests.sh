#!/bin/bash
# run-predeploy-tests.sh
# Script to catch common bugs (like AttributeError or parsing issues) before building Docker images.

echo "--- Running Pre-deployment Tests ---"

# Ensure we are in the right directory
CDIR=$(dirname "$0")
cd "$CDIR"

# Ensure PYTHONPATH is set so tests can find main.py and utils.py
export PYTHONPATH=$PYTHONPATH:.

# Run the mock-based unit tests
echo -e "\n1. Running Unit Tests (Mock Browser)..."
.venv/bin/python -m pytest tests/test_browser_manager.py
if [ $? -eq 0 ]; then
    echo "✅ Unit tests passed."
else
    echo "❌ Unit tests failed! Check for Python errors, typos, or logic bugs."
    exit 1
fi

# Run the parsing snapshot tests
echo -e "\n2. Running Parsing Tests (HTML Snapshots)..."
.venv/bin/python -m pytest tests/test_parsing_snapshots.py
if [ $? -eq 0 ]; then
    echo "✅ Parsing tests passed."
else
    echo "❌ Parsing tests failed! Sister portal layout might have changed or parsing logic is broken."
    exit 1
fi

echo -e "\n--- All pre-deployment tests passed! ---"
echo "You can now proceed with 'docker compose build' and deployment."
