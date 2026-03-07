#!/bin/bash
set -e

APP_MODE=${APP_MODE:-BOTH}

echo "Starting Visura Service in mode: $APP_MODE"

case "$APP_MODE" in
  "API")
    echo "Starting only FastAPI on port 8000..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
    ;;
  "MCP")
    echo "Starting internal FastAPI and MCP SSE on port 8001..."
    # Start FastAPI in background (internal only)
    uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 &
    # Start MCP server in SSE mode
    # FastMCP run() with transport="sse" usually starts a uvicorn server
    # We use the python command since we want to pass arguments
    export VISURA_API_URL="http://127.0.0.1:8000"
    exec fastmcp run visura_mcp/server.py --transport sse --port 8001 --host 0.0.0.0
    ;;
  "BOTH")
    echo "Starting both FastAPI (8000) and MCP (8001)..."
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 &
    export VISURA_API_URL="http://127.0.0.1:8000"
    exec fastmcp run visura_mcp/server.py --transport sse --port 8001 --host 0.0.0.0
    ;;
  *)
    echo "Unknown APP_MODE: $APP_MODE. Defaulting to BOTH."
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 &
    exec fastmcp run visura_mcp/server.py --transport sse --port 8001 --host 0.0.0.0
    ;;
esac
