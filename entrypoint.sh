#!/bin/bash
set -e

# Start Xvfb for Playwright if not already running (mostly for completeness in headless envs)
if [ -n "$DISPLAY" ] && [ "$DISPLAY" == ":99" ]; then
    echo "Starting Xvfb on :99..."
    Xvfb :99 -screen 0 1280x1024x24 &
    sleep 2
fi

# Execute the passed command
echo "Executing: $@"
exec "$@"
