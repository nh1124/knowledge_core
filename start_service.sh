#!/bin/bash
# Start Antigravity Cortex (Knowledge Core) Service

echo "Starting Antigravity Cortex..."
echo ""

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Start docker-compose
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d
else
    echo "WARNING: docker-compose not found. Database might not be running."
fi

# Set host and port
HOST=${HOST:-0.0.0.0}

# Prioritize KC_HOST_PORT for the local listener to match Windows behavior
if [ -n "$KC_HOST_PORT" ]; then
    PORT=$KC_HOST_PORT
else
    PORT=${PORT:-8200}
fi

echo ""
echo "TIP: Ensure your database is running (e.g., docker-compose up -d)"
echo ""

echo "Starting Antigravity Cortex on $HOST:$PORT..."
echo "UI will be available at http://localhost:$PORT/ui"
echo ""

uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
