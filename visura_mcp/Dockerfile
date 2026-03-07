# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Create and switch to a non-root user
RUN useradd -m -u 1000 appuser
WORKDIR /app

# Install dependencies
COPY visura_mcp/requirements.txt ./visura_mcp/
RUN pip install --no-cache-dir -r visura_mcp/requirements.txt

# Copy only the MCP folder and its docs
COPY --chown=appuser:appuser visura_mcp/ ./visura_mcp/

# Switch to the non-root user
USER appuser

# Expose MCP port
EXPOSE 8001

# Default command for MCP server (SSE mode)
CMD ["fastmcp", "run", "visura_mcp/server.py", "--transport", "sse", "--port", "8001", "--host", "0.0.0.0"]
