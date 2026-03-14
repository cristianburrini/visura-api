FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for postgres and mysql drivers
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into memory package
COPY . ./memory/

# Set PYTHONPATH so 'memory' package is found
ENV PYTHONPATH=/app

# Expose Proxy Port
EXPOSE 8000

# Default command
CMD ["uvicorn", "memory.main:app", "--host", "0.0.0.0", "--port", "8000"]
