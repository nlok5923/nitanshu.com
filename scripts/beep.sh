#!/bin/bash
  set -e

  # Install Claude Code beep hook
  # Plays a sound when Claude finishes a task (macOS only)

  HOOK_DIR="$HOME/.claude/hooks"
  HOOK_FILE="$HOOK_DIR/beep.sh"
  SETTINGS="$HOME/.claude/settings.json"

  # Check macOS
  if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This hook requires macOS (uses afplay)."
    exit 1
  fi

  # Install jq if missing
  if ! command -v jq &>/dev/null; then
    echo "jq not found, installing via Homebrew..."
    if ! command -v brew &>/dev/null; then
      echo "Error: Homebrew is required. Install it from https://brew.sh"
      exit 1
    fi
    brew install jq
  fi

  # Create hook script
  mkdir -p "$HOOK_DIR"
  cat > "$HOOK_FILE" << 'EOF'
  #!/bin/bash
  afplay /System/Library/Sounds/Glass.aiff
  exit 0
  EOF
  chmod +x "$HOOK_FILE"
  echo "Created $HOOK_FILE"

  # Merge hook into ~/.claude/settings.json
  HOOK_JSON=$(cat << EOF
  {
    "hooks": {
      "Stop": [
        {
          "hooks": [
            {
              "type": "command",
              "command": "$HOOK_FILE"
            }
          ]
        }
      ]
    }
  }
  EOF
  )

  if [ -f "$SETTINGS" ]; then
    jq --argjson h "$HOOK_JSON" '. * $h' "$SETTINGS" > /tmp/.claude-tmp.json
    mv /tmp/.claude-tmp.json "$SETTINGS"
  else
    mkdir -p "$HOME/.claude"
    echo "$HOOK_JSON" > "$SETTINGS"
  fi

  echo "Updated $SETTINGS"
  echo ""
  echo "Done! Claude Code will now beep when it finishes a task."