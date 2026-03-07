# Visura MCP Server

This directory contains the Model Context Protocol (MCP) server for the Visura API. It allows AI agents to interact with the Italian cadastral system (SISTER) in a structured and documented way.

## Features
- **Tools**: Perform visuras, retrieve results, and search for property owners.
- **Resources**: High-quality documentation, including OpenAPI specs and Arazzo workflows for complex orchestration.
- **Prompts**: Pre-defined prompts to help agents start their journey correctly.

## Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment:
   Make sure `VISURA_API_URL` is set to the location of your running `visura-api`.

## Running the Server
You can run the server in stdio mode (for local use) or SSE mode (for remote use).

### Stdio Mode
```bash
python server.py
```

### SSE Mode (Remote)
Use the Docker configuration with `APP_MODE=MCP`.

## Testing
Use the provided script:
```bash
./scripts/test_mcp.sh
```
This will launch the MCP Inspector.
