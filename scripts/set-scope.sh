#!/usr/bin/env bash
# Read or write the ursula voice-profile scope.
#
# The scope controls when the voice profile is applied:
#   all     → every output, including conversational replies (default).
#   compose → only when Claude is ghost-writing prose on the user's behalf
#             (outbound messages, drafts, docs, commits, PRs, etc.). Direct
#             conversational replies use a neutral register.
#
# Usage:
#   scripts/set-scope.sh                # Print current scope
#   scripts/set-scope.sh --show         # Same as above
#   scripts/set-scope.sh all            # Set scope to "all"
#   scripts/set-scope.sh compose        # Set scope to "compose"
#   scripts/set-scope.sh --toggle       # Flip between all <-> compose
#
# The new value takes effect on the next Claude Code session start (the
# SessionStart hook reads ~/.ursula/config.json fresh each time).

set -euo pipefail

CONFIG_DIR="$HOME/.ursula"
CONFIG_PATH="$CONFIG_DIR/config.json"

read_scope() {
    python3 - "$CONFIG_PATH" <<'PY'
import json, sys
path = sys.argv[1]
scope = "all"
try:
    with open(path) as f:
        cfg = json.load(f)
    candidate = cfg.get("scope")
    if candidate in ("all", "compose"):
        scope = candidate
except Exception:
    pass
print(scope)
PY
}

write_scope() {
    local new_scope="$1"
    mkdir -p "$CONFIG_DIR"
    python3 - "$CONFIG_PATH" "$new_scope" <<'PY'
import json, os, sys
path, new_scope = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}
cfg["scope"] = new_scope
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
}

case "${1:-}" in
    ""|--show|-s)
        scope="$(read_scope)"
        echo "scope=$scope (config: $CONFIG_PATH)"
        exit 0
        ;;
    --toggle|-t)
        current="$(read_scope)"
        if [[ "$current" == "all" ]]; then
            new="compose"
        else
            new="all"
        fi
        write_scope "$new"
        echo "scope: $current -> $new"
        exit 0
        ;;
    all|compose)
        write_scope "$1"
        echo "scope set to: $1"
        exit 0
        ;;
    *)
        echo "Usage: $0 [all|compose|--toggle|--show]" >&2
        exit 2
        ;;
esac
