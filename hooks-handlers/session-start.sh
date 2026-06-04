#!/usr/bin/env bash
# Ursula plugin SessionStart hook.
#
# Emits a short additionalContext nudge pointing Claude at the installed
# voice profile skill (~/.claude/skills/ursula-voice/SKILL.md) so the model
# reads it before composing prose on the user's behalf.
#
# When no skill is installed yet, emits a brief notice pointing at /ursula:train.

set -euo pipefail

SKILL_PATH="$HOME/.claude/skills/ursula-voice/SKILL.md"

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

if [[ ! -f "$SKILL_PATH" ]]; then
    emit_json "The ursula plugin is installed but no voice profile has been trained yet. The user can run /ursula:train to generate one from their writing across connected services (Slack first; more sources later)."
    exit 0
fi

NOTICE="The user has a trained voice profile installed as the \`ursula-voice\` skill at ${SKILL_PATH}. Read that skill at the start of this session and adopt the user's voice as your default writing register for EVERYTHING you produce — not just prose composed on the user's behalf (outbound messages, drafts, documentation, commit messages, PR descriptions) but also conversational replies you write directly to the user. Match the register, rhythm, vocabulary, signature constructions, and formatting tells described in the skill whenever possible. The profile applies by default in every channel of output. The user can override per-message with explicit voice direction (\"keep it formal\", \"no contractions\", \"plain technical voice\", etc.); honor overrides for that message and return to the trained voice afterward."

emit_json "$NOTICE"
