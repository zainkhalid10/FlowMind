#!/bin/bash

# FlowMind Quick Start Script for Ubuntu/WSL

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Starting FlowMind..."
echo "========================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Please run setup_ubuntu.sh first.${NC}"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing now...${NC}"
    pip install -r requirements.txt
fi

# Check if database exists
if [ ! -f "flowmind.db" ]; then
    echo "Initializing database..."
    python3 -c "from database import init_db; init_db()"
fi

# Create directories if they don't exist
mkdir -p uploads chroma_db

# Check if Ollama is running (optional)
if command -v ollama &> /dev/null; then
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Starting Ollama service..."
        ollama serve > /dev/null 2>&1 &
        sleep 2
    fi
fi

echo -e "${GREEN}Starting FlowMind server...${NC}"
echo ""
echo "Access the application at:"
echo "  - http://localhost:8000"
echo "  - API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application with uvicorn
uvicorn flowmind:app --host 0.0.0.0 --port 8000

