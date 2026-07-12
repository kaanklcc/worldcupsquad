#!/bin/bash

echo "Starting Auto-Gaffer Backend..."
echo ""

# Check if uvicorn is installed
python -c "import uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the server
echo "Starting server on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000