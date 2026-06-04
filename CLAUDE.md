# Ursula — agent orientation

Ursula is a Claude Code plugin that builds a voice/style profile of the user from their writing across connected services (Slack, Google Drive, others as added) and installs it as a session-time skill so future Claude sessions write in the user's voice by default.

Sibling to imprint (behavioral profile) — ursula is the voice profile.

## Hard constraints

- This is the user's personal repo under github.com:n33kos/ursula. All commits must use `nick@suskitech.org` — verify with `git log -1 --format='%ae'` before pushing. NEVER commit under `nicholas.suski@babylist.com`.
- Mirror imprint's plugin shape (.claude-plugin/, hooks/, scripts/, skills/, templates/).
- The voice profile is a markdown skill file that gets auto-loaded at session start.
