# ursula

A Claude Code plugin that mines your writing across connected services to build a high-fidelity linguistic profile of how you sound — then installs that profile as a skill that biases every Claude session to write in your voice.

Sibling project to [imprint](https://github.com/n33kos/imprint), which captures behavioral patterns. Ursula captures **voice**: prose rhythm, terminology, tone, layering, signature constructions.

## Status

Walking skeleton (v0.1.0). One source wired up — Slack. Google Drive, email, Notion, etc. land in future versions.

## Installation

```
/plugin install n33kos/ursula
```

## Usage

### Train your voice profile

```
/ursula:train
```

The skill will:

1. Ask a few configuration questions (time window, synthesis model, sample cap).
2. Resolve your Slack user via the Slack MCP and page through search results for messages you've authored in the chosen window.
3. Save the raw responses to `~/.ursula/samples/slack/raw/`.
4. Normalize them into a clean samples file at `~/.ursula/samples/slack/messages.json`.
5. Run a multi-pass forensic-linguistics synthesis via `claude --print` to produce a structured voice profile at `~/.ursula/profile/SKILL.md`.
6. Install the profile as a user-level skill at `~/.claude/skills/ursula-voice/SKILL.md`.

### How the profile gets loaded

A `SessionStart` hook (`hooks/hooks.json` → `hooks-handlers/session-start.sh`) fires on every Claude Code session start, resume, clear, and compact. It emits a short `additionalContext` nudge pointing Claude at the installed `ursula-voice` skill so the model reads it before composing any prose on your behalf.

If no profile has been trained yet, the hook emits a notice pointing at `/ursula:train` instead.

### Profile contents

The synthesized profile covers, with linguistics terminology where it adds precision:

- **Register & Tone** — sociolinguistic register, audience-conditioned shifts
- **Sentence-Length Distribution & Rhythm** — mean/modal length, paragraph rhythm
- **Syntactic Preferences** — parataxis vs hypotaxis, fragments, em-dash habits
- **Lexical Fingerprint** — signature vocabulary, density, avoided phrases
- **Hedging, Intensifiers & Stance Markers** — confidence signaling inventory
- **Signature Constructions** — multi-word patterns that recur and feel distinctly yours
- **Formatting Habits** — capitalization, punctuation tells, emoji, markdown
- **Discourse & Layering** — long-form structure, asides, anticipation of pushback
- **Voice in Reply vs Composed Prose** — delta between modes
- **Imitation Quick-Reference** — actionable rules an imitator should follow

### Locations

- Raw samples: `~/.ursula/samples/<source>/raw/`
- Normalized samples: `~/.ursula/samples/<source>/messages.json`
- Synthesized profile: `~/.ursula/profile/SKILL.md`
- Installed skill: `~/.claude/skills/ursula-voice/SKILL.md`

All of these live outside the plugin install dir so they survive plugin updates. You can hand-edit the installed skill to correct or refine the profile.

### Uninstalling the profile

```
bash $CLAUDE_PLUGIN_ROOT/scripts/install-profile.sh --remove
```

## Roadmap

- Additional sources: Google Drive, Gmail, Notion, GitHub PR descriptions.
- Deterministic statistical features (avg sentence length, lexical density, n-gram fingerprints) alongside LLM synthesis for stability across runs.
- Periodic re-training (cron / hook).
- Profile diff between training runs.
