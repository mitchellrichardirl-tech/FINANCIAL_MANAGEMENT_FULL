#!/bin/bash

# Fix SSH key permissions if mounted from Windows
if [ -d "$HOME/.ssh" ]; then
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/id_"* 2>/dev/null || true
    chmod 644 "$HOME/.ssh/*.pub" 2>/dev/null || true
fi

# Install system dependencies
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils keychain

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH for current session
export PATH="$HOME/.cargo/bin:$PATH"

# Install Python dependencies with uv
uv sync --all-groups

# Install the project itself as an editable package
uv pip install -e .

# Register Jupyter kernel
source .venv/bin/activate
python -m ipykernel install --user --name=financial-management

echo 'eval $(keychain --eval --agents ssh --quiet id_ed25519 2>/dev/null)' >> "$HOME/.bashrc"