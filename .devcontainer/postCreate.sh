#!/bin/bash

# Fix SSH key permissions if mounted from Windows
if [ -d "$HOME/.ssh" ]; then
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/id_"* 2>/dev/null || true
    chmod 644 "$HOME/.ssh/*.pub" 2>/dev/null || true
fi

# System dependencies
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils keychain curl ca-certificates libgl1 libglib2.0-0
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Backend setup
cd backend
uv sync --all-groups
uv pip install -e .
source .venv/bin/activate
python -m ipykernel install --user --name=financial-management
cd ..

# Frontend setup
cd "$PWD/frontend" && npm install

echo 'eval $(keychain --eval --agents ssh --quiet id_ed25519 2>/dev/null)' >> "$HOME/.bashrc"
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> "$HOME/.bashrc"