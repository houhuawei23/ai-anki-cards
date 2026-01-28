#!/bin/bash
# AnkiGen wrapper script
# 确保在项目目录下以模块方式运行 ankigen

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
python -m ankigen "$@"

# 在 ~/.zshrc 中添加 alias ankigen="$MY_SCRIPTS_DIR/ai-anki-cards/ankigen_wrapper.sh"
