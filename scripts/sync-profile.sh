#!/usr/bin/env bash
# Sync the installed voice profile back to the canonical copy, optionally
# logging a one-line refinement summary.
#
# The installed copy at ~/.claude/skills/ursula-voice/SKILL.md is treated as
# the source of truth — that's the file Claude actually reads at session
# start. The canonical archival copy at ~/.ursula/profile/SKILL.md is kept in
# lockstep so it survives plugin updates and reinstalls.
#
# Usage:
#   sync-profile.sh                          # cp installed -> canonical
#   sync-profile.sh --summary "what changed" # cp + append to refinements.log
#   sync-profile.sh --check                   # report drift, no copy
#
# Exit codes:
#   0 = success / in-sync
#   1 = installed profile missing
#   2 = --check found drift between installed and canonical

set -euo pipefail

INSTALLED="$HOME/.claude/skills/ursula-voice/SKILL.md"
CANONICAL_DIR="$HOME/.ursula/profile"
CANONICAL="$CANONICAL_DIR/SKILL.md"
LOG_PATH="$HOME/.ursula/refinements.log"

mode="sync"
summary=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)
            mode="check"
            shift
            ;;
        --summary)
            if [[ $# -lt 2 ]]; then
                echo "--summary requires a value" >&2
                exit 1
            fi
            summary="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,/^$/p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [[ ! -f "$INSTALLED" ]]; then
    echo "No installed profile found at $INSTALLED" >&2
    echo "Run /ursula:train to generate one." >&2
    exit 1
fi

if [[ "$mode" == "check" ]]; then
    if [[ ! -f "$CANONICAL" ]]; then
        echo "canonical-missing"
        exit 0
    fi
    if diff -q "$INSTALLED" "$CANONICAL" >/dev/null; then
        echo "in-sync"
        exit 0
    fi
    echo "drift"
    diff -u "$CANONICAL" "$INSTALLED" >&2 || true
    exit 2
fi

mkdir -p "$CANONICAL_DIR"
cp "$INSTALLED" "$CANONICAL"
echo "synced $INSTALLED -> $CANONICAL"

if [[ -n "$summary" ]]; then
    mkdir -p "$(dirname "$LOG_PATH")"
    ts="$(date +%Y-%m-%dT%H:%M:%S)"
    printf '%s\t%s\n' "$ts" "$summary" >> "$LOG_PATH"
    echo "logged: $summary"
fi
