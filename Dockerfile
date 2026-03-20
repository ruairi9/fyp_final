FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (kubectl, vagrant ssh support, ping, iostat)
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    sysstat \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all dashboard files
COPY home.py .
COPY dashboard.py .
COPY server_dashboard.py .
COPY pipeline_dashboard.py .
COPY developer_workspace.py .
COPY run-all.sh .

RUN chmod +x run-all.sh

# Expose all dashboard ports
EXPOSE 5000 6001 7000 8080 9000

# Default: run all services
CMD ["bash", "run-all.sh"]
