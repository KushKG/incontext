#!/bin/bash

# Start the FastAPI backend server
echo "Starting Timeline Generator Backend..."
echo "Make sure you have set up your .env file with OPENAI_API_KEY"
echo ""

cd backend
python main.py 