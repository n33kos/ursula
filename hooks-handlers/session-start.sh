#!/usr/bin/env bash
# Ursula plugin SessionStart hook.
#
# Emits an additionalContext nudge pointing Claude at the installed voice
# profile skill (~/.claude/skills/ursula-voice/SKILL.md). The exact instruction
# depends on the user's configured scope:
#
#   scope=all     → voice profile applies to EVERYTHING Claude writes,
#                   including direct conversational replies (default).
#   scope=compose → voice profile applies only when Claude is composing prose
#                   on the user's behalf (outbound messages, drafts, docs,
#                   commit messages, PR descriptions, etc.). Direct
#                   conversational replies use a neutral register unless the
#                   user explicitly invokes the voice.
#
# The scope is read fresh from ~/.ursula/config.json on every session start so
# toggling takes effect immediately on the next session. Unknown or missing
# values fall back to "all" (the historical default).
#
# When no skill is installed yet, emits a brief notice pointing at /ursula:train.

set -euo pipefail

SKILL_PATH="$HOME/.claude/skills/ursula-voice/SKILL.md"
CONFIG_PATH="$HOME/.ursula/config.json"

emit_json() {
    # JSON-encode the body as additionalContext. python3 is always present on macOS.
    python3 - "$1" <<'PY'
import json, sys
body = sys.argv[1]
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": body,
    }
}))
PY
}

read_scope() {
    # Read scope from ~/.ursula/config.json. Returns "all" or "compose".
    # Falls back to "all" on any error (missing file, malformed JSON,
    # unknown value). Never fails the hook.
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

if [[ ! -f "$SKILL_PATH" ]]; then
    emit_json "The ursula plugin is installed but no voice profile has been trained yet. The user can run /ursula:train to generate one from their writing across connected services (Slack first; more sources later)."
    exit 0
fi

SCOPE="$(read_scope)"

if [[ "$SCOPE" == "compose" ]]; then
    NOTICE="The user has a trained voice profile installed as the \`ursula-voice\` skill at ${SKILL_PATH}. The user has configured ursula's scope as \"compose\": apply the voice profile ONLY when composing prose on the user's behalf — outbound messages (Slack, email, IM), drafts, documentation, commit messages, PR descriptions, and any other text the user will send or publish as themselves. For direct conversational replies back to the user inside this Claude session, do NOT adopt the voice; use a neutral, professional default register instead. The user can opt-in per message with explicit voice direction (\"reply as me\", \"in my voice\", \"sound like me\") — honor that override for the message and return to neutral afterward. To change the scope, run /ursula:scope or edit ${HOME}/.ursula/config.json."
else
    NOTICE="The user has a trained voice profile installed as the \`ursula-voice\` skill at ${SKILL_PATH}. The user has configured ursula's scope as \"all\": adopt the user's voice as your default writing register for EVERYTHING you produce — not just prose composed on the user's behalf (outbound messages, drafts, documentation, commit messages, PR descriptions) but also conversational replies you write directly to the user. Match the register, rhythm, vocabulary, signature constructions, and formatting tells described in the skill whenever possible. The user can override per-message with explicit voice direction (\"keep it formal\", \"no contractions\", \"plain technical voice\", etc.); honor overrides for that message and return to the trained voice afterward. To change the scope, run /ursula:scope or edit ${HOME}/.ursula/config.json."
fi

emit_json "$NOTICE"
