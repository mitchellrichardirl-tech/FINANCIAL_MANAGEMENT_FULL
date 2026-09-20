#!/usr/bin/env bash
# Usage: scripts/new-worktree.sh <branch> [--with-uploads]
set -euo pipefail

branch="$1"; shift || true
root="$(git rev-parse --show-toplevel)"
dir="$root/.worktrees/$branch"

git worktree add "$dir" "$branch" 2>/dev/null || git worktree add -b "$branch" "$dir"

# The .env has secrets and no paths, so copying it is safe.
cp "$root/backend/.env" "$dir/backend/.env"

# Snapshot the dev database. VACUUM INTO handles WAL mode correctly.
mkdir -p "$dir/backend/data-dev/uploads"
python3 - "$root/backend/data-dev/financial_data.db" "$dir/backend/data-dev/financial_data.db" <<'EOF'
import sqlite3, sys
src, dst = sys.argv[1:]
con = sqlite3.connect(src)
con.execute("VACUUM INTO ?", (dst,))
con.close()
EOF

# Receipt images are optional. Without them, old receipts show no image.
if [[ "${1:-}" == "--with-uploads" ]]; then
  cp -r "$root/backend/data-dev/uploads/." "$dir/backend/data-dev/uploads/"
fi

(cd "$dir/backend" && uv sync)
(cd "$dir/frontend" && npm ci)

echo "Worktree ready: $dir"