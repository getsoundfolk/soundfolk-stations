#!/usr/bin/env bash
# Fast check run by the Claude Code Stop hook when tracked files changed (from the repository root).
set -euo pipefail

python3 scripts/lint.py
