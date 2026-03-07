#!/bin/bash
# Script to simplify testing the MCP server using the inspector.
# It assumes you have node and npx installed.

echo "Launching MCP Inspector for visura_mcp/server.py..."
npx @modelcontextprotocol/inspector python visura_mcp/server.py
