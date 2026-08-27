#!/usr/bin/env bash
# Copies the ViralDzen skill into Cursor / Claude Code / Codex user dirs
# and installs the Python CLI so `python3 -m viraldzen` works anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$ROOT/skills/viraldzen-collect"

if [[ ! -f "$SKILL_SRC/SKILL.md" ]]; then
  echo "SKILL.md not found at $SKILL_SRC" >&2
  exit 1
fi

copy_skill() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  cp -R "$SKILL_SRC" "$dest"
  echo "skill → $dest"
}

copy_skill "${HOME}/.cursor/skills/viraldzen-collect"
copy_skill "${HOME}/.agents/skills/viraldzen-collect"
copy_skill "${HOME}/.claude/skills/viraldzen-collect"

if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install -e "$ROOT"
else
  echo "python3 not found; install Python 3.11+ and run: python3 -m pip install -e \"$ROOT\"" >&2
  exit 1
fi

echo
echo "Готово. В Cursor / Claude Code / Codex скилл viraldzen-collect уже на месте."
echo "Проверка CLI: python3 -m viraldzen -h"
