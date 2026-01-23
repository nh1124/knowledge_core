#!/bin/bash
# Reset Antigravity Cortex (Knowledge Core) Environment

echo "Resetting Antigravity Cortex environment..."
echo ""

# Stop and remove containers and volumes
echo "Stopping Docker containers and removing volumes..."
docker-compose down -v

# Remove log files
echo "Cleaning up logs..."
rm -rf logs/*.log

# Optionally, remove __pycache__
echo "Cleaning up Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} +

echo ""
echo "Initialization complete. To start the service, run:"
echo "./start_service.sh"
echo ""
