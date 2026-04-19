#!/bin/bash
# TermBot CLI Launcher
# Quick start script for the interactive CLI

cd "$(dirname "$0")"

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Run the CLI
python3 start.py "$@"
