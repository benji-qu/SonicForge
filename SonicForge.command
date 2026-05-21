#!/bin/bash
# Navigate to the directory where this script is located
cd "$(dirname "$0")"

# Activate the virtual environment
source .venv/bin/activate

# Run the application
python3 main.py
