#!/bin/bash

echo "=========================================="
echo "Code Upload & Test System"
echo "=========================================="
echo ""

# Check if file provided
if [ -z "$1" ]; then
    echo "Usage: ./upload-code.sh <python-file>"
    echo "Example: ./upload-code.sh user_code.py"
    exit 1
fi

CODE_FILE=$1

# Check file exists
if [ ! -f "$CODE_FILE" ]; then
    echo "Error: File '$CODE_FILE' not found!"
    exit 1
fi

echo "📁 File: $CODE_FILE"
echo "📊 Size: $(wc -c < $CODE_FILE) bytes"
echo "📝 Lines: $(wc -l < $CODE_FILE) lines"
echo ""

# Set kubectl config
export KUBECONFIG=./k3s.yaml

# Copy to Jenkins
echo "⬆️  Uploading to Jenkins..."
kubectl cp "$CODE_FILE" cicd/jenkins-b74dbbb-l7tbd:/tmp/user_code.py

if [ $? -eq 0 ]; then
    echo "✅ Upload successful!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Go to Jenkins: http://192.168.121.40:32080"
    echo "2. Click on 'user-code-test' pipeline"
    echo "3. Click 'Build Now'"
    echo "4. Watch your code being tested!"
else
    echo "❌ Upload failed!"
    exit 1
fi
