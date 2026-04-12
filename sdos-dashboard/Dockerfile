FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    vagrant \
    libvirt-clients \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/v1.28.5/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Python dependencies
RUN pip install --no-cache-dir flask requests

# Copy dashboard files
COPY . .

EXPOSE 5000 6001 7000 8080 9000
