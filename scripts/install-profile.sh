#!/usr/bin/env bash
# Install the synthesized voice profile as a Claude Code skill.
#
# Copies ~/.ursula/profile/SKILL.md to ~/.claude/skills/ursula-voice/SKILL.md
# so it's auto-discovered as a user-level skill in every Claude session.
#
# Usage:
#   scripts/install-profile.sh              # Install / refresh
#   scripts/install-profile.sh --check      # Report status only
#   scripts/install-profile.sh --remove     # Uninstall (with confirmation)

set -euo pipefail

SRC="$HOME/.ursula/profile/SKILL.md"
DEST_DIR="$HOME/.claude/skills/ursula-voice"
DEST="$DEST_DIR/SKILL.md"

case "${1:-}" in
    --check)
        if [[ -f "$DEST" ]]; then
            lines=$(wc -l < "$DEST")
            size=$(wc -c < "$DEST")
            echo "Installed at $DEST ($lines lines, $size bytes)"
        else
            echo "Not installed. Run /ursula:train to generate and install."
        fi
        exit 0
        ;;
    --remove)
        if [[ -d "$DEST_DIR" ]]; then
            read -p "Remove voice profile skill at $DEST_DIR? [y/N] " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                rm -rf "$DEST_DIR"
                echo "Removed."
            else
                echo "Cancelled."
            fi
        else
            echo "Nothing to remove — $DEST_DIR does not exist."
        fi
        exit 0
        ;;
esac

if [[ ! -f "$SRC" ]]; then
    echo "Error: source profile not found at $SRC" >&2
    echo "Run the synthesizer first (scripts/synthesize-profile.py)." >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"

lines=$(wc -l < "$DEST")
size=$(wc -c < "$DEST")
echo "Installed voice profile to $DEST ($lines lines, $size bytes)"
