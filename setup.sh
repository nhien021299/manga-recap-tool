#!/bin/bash
# Setup script for Manhwa Recap Tool (Linux/Mac)

echo -e "\033[0;36m--- Manhwa Recap Tool Setup ---\033[0m"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "python3 could not be found. Please install Python 3.10 or higher."
    exit 1
fi

# 2. Setup Backend
echo -e "\n\033[0;33m[1/4] Setting up backend environment...\033[0m"
cd backend
if [ ! -d ".bench/vieneu-venv" ]; then
    python3 -m venv .bench/vieneu-venv
fi
source .bench/vieneu-venv/bin/activate
pip install -r requirements.txt
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "\033[0;32mCreated backend/.env from example.\033[0m"
fi
cd ..

# 3. Setup Frontend
echo -e "\n\033[0;33m[2/4] Setting up frontend environment...\033[0m"
cd web-app
npm install
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "\033[0;32mCreated web-app/.env from example.\033[0m"
fi
cd ..

# 4. Check Models
echo -e "\n\033[0;33m[3/4] Checking local models...\033[0m"
if [ ! -d "backend/.models/f5-onnx/CPU_F32" ]; then
    echo -e "\033[0;35mWarning: F5 ONNX models not found in backend/.models/f5-onnx/\033[0m"
else
    echo -e "\033[0;32mF5 ONNX models found.\033[0m"
fi

# 5. Success
echo -e "\n\033[0;36m[4/4] Setup complete!\033[0m"
echo -e "\nTo start development:"
echo "1. npm run dev:be"
echo "2. npm run dev:web"
