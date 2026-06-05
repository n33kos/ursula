---
name: ursula:train
description: Train a voice profile from the user's writing across connected services (Slack first), then install it as a session-time skill.
---

# Train Voice Profile

End-to-end pipeline: collect writing samples from connected services → synthesize a forensic-linguistics voice profile → install as a Claude Code skill so every future session writes in the user's voice by default.

## Prerequisites

- Slack MCP must be available in this session (`mcp__plugin_slack_slack__*` tools). If not, ask the user to enable the Slack plugin/MCP before running this skill.
- `claude` CLI must be on PATH (used by the synthesizer for multi-pass synthesis).
- `python3` must be on PATH (macOS default).

## Configuration (ask one at a time, recommend defaults)

### Question 1: Time window

> **How far back should I pull writing samples?**
>
> 1. **Last 90 days** *(recommended)* — broad search window; ample tail to fish from
> 2. **Last 30 days** — quick snapshot
> 3. **Custom** — you specify in days

Resolve the chosen window to an `after:YYYY-MM-DD` Slack search modifier. The time window is the *search* bound — the actual collected sample count is gated by the page cap below.

### Question 2: Model

> **Which model should I use for synthesis?**
>
> 1. **Opus** — highest quality and depth
> 2. **Sonnet** *(recommended)* — strong quality, moderate cost
> 3. **Haiku** — fastest, shallowest

Map to `--model {opus|sonnet|haiku}`.

### Question 3: Thoroughness (page cap)

> **How thoroughly should I page through Slack results?**
>
> 1. **Standard (6 pages, ~120 messages)** *(recommended)* — solid voice signal, modest token cost
> 2. **Deep (10 pages, ~200 messages)** — richer corpus, noticeably higher token cost
> 3. **Quick (3 pages, ~60 messages)** — fastest pass; works because voice signal saturates quickly

Use the chosen page cap as the hard stop in step 2. Pages are 20 messages each. **Architectural note for transparency:** each page response flows through this session's context window before being archived to disk via `Write`, so cost scales linearly with page count. There's no token-free way to pull hundreds of pages under the current MCP-driven design — that's a known limitation, not a bug. A future iteration may add a Slack-Web-API-based collector that bypasses the context window entirely.

### Question 4: Scope (when should the voice apply?)

> **When should the trained voice profile apply?**
>
> 1. **All output (`all`)** *(recommended)* — Claude adopts your voice for everything it writes, including conversational replies back to you inside Claude Code sessions.
> 2. **Composed prose only (`compose`)** — Claude only adopts your voice when ghost-writing on your behalf (Slack drafts, emails, docs, commit messages, PR descriptions, etc.). Direct conversational replies use a neutral register unless you explicitly opt in per message.

This setting is saved to `~/.ursula/config.json` and read by the `SessionStart` hook on every new session, so it can be changed later with `/ursula:scope`.

---

Once the user has answered (or accepted defaults), confirm the choices and proceed.

## Step 1: Resolve the user's Slack identity

Call `mcp__plugin_slack_slack__slack_read_user_profile` with no arguments (or with `user: "me"`) to get the authenticated user's Slack user ID. Save the user ID — you'll need it as the `from:` modifier in the next step. Do NOT proceed if you cannot resolve a concrete user ID; ask the user instead.

## Step 2: Collect raw Slack samples

Create the raw samples directory:

```bash
mkdir -p ~/.ursula/samples/slack/raw
rm -f ~/.ursula/samples/slack/raw/*.json   # Clear stale runs
```

Page through Slack search using `mcp__plugin_slack_slack__slack_search_public_and_private`. Use a query like:

```
from:<USER_ID> after:<YYYY-MM-DD>
```

For each page of results:

1. Save the **raw response** to `~/.ursula/samples/slack/raw/page-NN.json` (zero-padded page number) using the `Write` tool. The MCP returns a markdown blob under a top-level `results` field; saving the blob text as-is is fine — the normalizer handles both JSON envelopes and bare markdown.
2. Follow the `next_cursor` / pagination cue in the response and request the next page.
3. Stop when there are no more results OR when you've written the chosen page-cap number of files (Quick = 3, Standard = 6, Deep = 10). Do **not** exceed the cap — it's the user's stated token-cost ceiling.

If the user has DMs and group DMs that aren't searchable via the public search, that's fine — the walking-skeleton corpus is public + private channel messages.

## Step 3: Normalize samples

Run the collector script to dedupe, strip Slack-flavored markup, drop voiceless messages (link-only, mention-only, automod), and produce a clean samples file:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/collect-slack.py" \
    --raw-dir ~/.ursula/samples/slack/raw \
    --output ~/.ursula/samples/slack/messages.json
```

Confirm the output reports a reasonable sample count (≥ 30 ideally). If it's far lower than expected, surface that to the user — the profile will be thin — and ask whether to proceed, widen the time window, or stop.

## Step 4: Synthesize

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/synthesize-profile.py" \
    ~/.ursula/samples/slack/messages.json \
    --model <MODEL>
```

This writes the synthesized profile to `~/.ursula/profile/SKILL.md` (already wrapped in skill frontmatter).

## Step 5: Save scope config

Persist the user's Question-4 answer so the SessionStart hook can read it:

```bash
bash "$CLAUDE_PLUGIN_ROOT/scripts/set-scope.sh" <all|compose>
```

Use whichever scope the user chose (or `all` if they accepted the default). If the user never explicitly answered Question 4, default to `all` and tell them so they aren't surprised.

## Step 6: Install

```bash
bash "$CLAUDE_PLUGIN_ROOT/scripts/install-profile.sh"
```

This copies the profile to `~/.claude/skills/ursula-voice/SKILL.md` so Claude Code auto-discovers it as a user-level skill. The SessionStart hook will pick it up on the next session start.

## Step 7: Report

1. Read `~/.claude/skills/ursula-voice/SKILL.md` and present a short summary to the user — top observations from each section (register, rhythm, signature constructions, formatting habits). Quote two or three of the most distinctive imitation-quick-reference rules verbatim.
2. Report the corpus stats: source(s), sample count, time window, total characters.
3. Note any sections the synthesizer flagged as `[low confidence]` due to thin signal.
4. Confirm the saved scope (`all` or `compose`) and remind the user they can change it later with `/ursula:scope`.
5. Remind the user the profile auto-loads in new sessions via the SessionStart hook. To regenerate, run `/ursula:train` again. To uninstall, run `bash $CLAUDE_PLUGIN_ROOT/scripts/install-profile.sh --remove`.

## Failure modes

- **Slack MCP not available** → stop and ask the user to enable the Slack plugin.
- **`slack_read_user_profile` returns no concrete user ID** → ask the user for their Slack user ID directly.
- **Zero search results** → surface the search query used and ask the user to confirm the time window / identity. Don't fabricate a profile.
- **`claude --print` fails or times out** → surface the synthesizer's stderr; suggest retry with `--model sonnet` or a longer `--timeout`.
- **Profile file empty or malformed after synthesis** → do NOT install. Report the issue and stop.
