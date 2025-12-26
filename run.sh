#!/bin/bash

# SENTINELX - Behavioral Biometric Authentication System
# Cross-platform startup script

echo "🔐 Starting SENTINELX System..."

# Detect operating system
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PYTHON_CMD="python"
    VENV_ACTIVATE="venv/Scripts/activate"
else
    PYTHON_CMD="python3"
    VENV_ACTIVATE="venv/bin/activate"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source $VENV_ACTIVATE

# Upgrade pip
echo "⬆️ Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "🗄️ Initializing database..."
python -c "from backend.database.db import init_database; init_database()"

# Create logs directory
mkdir -p logs

# Start the FastAPI server
echo "🚀 Starting SENTINELX server..."
echo "📊 Dashboard will be available at: http://localhost:8000"
echo "🔑 API docs available at: http://localhost:8000/docs"
echo "🔐 Login page at: http://localhost:8000/login.html"
echo ""
echo "Press Ctrl+C to stop the server"

# Run with Python module syntax to avoid import issues
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload