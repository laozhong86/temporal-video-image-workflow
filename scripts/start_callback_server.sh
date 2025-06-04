#!/bin/bash

# Start Kling Callback API Server
# This script starts the dedicated callback server on port 16883

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Kling Callback API Server..."
echo "Project root: $PROJECT_ROOT"
echo "Server will run on port 16883"
echo "Press Ctrl+C to stop the server"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch .deps_installed
fi

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Start the callback server
echo "Starting callback server on http://0.0.0.0:16883"
echo "Health check: http://localhost:16883/health"
echo "Callback endpoint: http://localhost:16883/callback/kling"
echo ""

python3 callback_server.py \
    --host 0.0.0.0 \
    --port 16883 \
    --temporal-host localhost:7233 \
    --temporal-namespace default \
    --reload