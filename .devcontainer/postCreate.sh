#!/bin/bash

# Install system dependencies
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH for current session
export PATH="$HOME/.cargo/bin:$PATH"

# Install Python dependencies with uv
uv sync