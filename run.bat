@echo off
REM SENTINELX - Behavioral Biometric Authentication System
REM Windows startup script

echo 🔐 Starting SENTINELX System...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Initialize database
echo 🗄️ Initializing database...
python -c "from backend.database.db import init_database; init_database()"

REM Create logs directory
if not exist "logs" mkdir logs

REM Start the FastAPI server
echo 🚀 Starting SENTINELX server...
echo 📊 Dashboard will be available at: http://localhost:8000
echo 🔑 API docs available at: http://localhost:8000/docs
echo 🔐 Login page at: http://localhost:8000/login.html
echo.
echo Press Ctrl+C to stop the server

REM Run with Python module syntax to avoid import issues
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause