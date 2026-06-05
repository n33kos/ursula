---
name: ursula:scope
description: Change when ursula's voice profile applies — to everything Claude writes (`all`) or only to prose Claude composes on the user's behalf (`compose`). Use when the user wants to toggle, set, or check the ursula scope. Triggers on phrases like "toggle ursula", "stop talking like me", "only use my voice for outbound stuff", "ursula scope", "set ursula to compose mode".
---

# Ursula Scope

Controls when the trained voice profile (`~/.claude/skills/ursula-voice/SKILL.md`) is applied. Two modes:

- **`all`** *(default)* — Claude adopts the user's voice for EVERYTHING it writes, including direct conversational replies inside Claude Code sessions.
- **`compose`** — Claude only adopts the voice when ghost-writing prose on the user's behalf (Slack drafts, emails, docs, commit messages, PR descriptions, etc.). Direct conversational replies use a neutral default register unless the user explicitly opts in for a message ("reply as me", "in my voice").

The setting lives at `~/.ursula/config.json` and is read fresh by the `SessionStart` hook on every session, so changes take effect on the next session start.

## How to act on user intent

### Set explicitly

If the user says something concrete — "set ursula to compose", "turn ursula off for normal chat", "only sound like me when I'm sending stuff" — set the scope directly:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/set-scope.sh" compose
# or
bash "${CLAUDE_PLUGIN_ROOT}/scripts/set-scope.sh" all
```

### Toggle

If the user says "toggle ursula" or "flip the ursula setting":

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/set-scope.sh" --toggle
```

### Show current

If the user just wants to know the current scope:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/set-scope.sh" --show
```

### Ambiguous request

If it's unclear which direction the user wants ("change the ursula thing"), first show the current scope, then ask the user which scope they want. Don't guess.

## Report back

After any change, tell the user:

1. The new scope value.
2. That the change applies to the **next** session start (the hook only reads the config at session boot — the current session's already-loaded instructions stay as-is until restart).
3. How to flip back if they change their mind (e.g., "run `/ursula:scope` again or `bash ${CLAUDE_PLUGIN_ROOT}/scripts/set-scope.sh --toggle`").
