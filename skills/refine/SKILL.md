---
name: ursula:refine
description: Surgically refine the trained voice profile in place. Use when the user notices the voice doing something undesirable (pet names, em-dashes, wrong register) or missing something present in their actual voice (a signature phrase, a register shift, an epistemic nuance). Triggers on phrases like "the profile is doing X and shouldn't", "refine ursula", "ursula is adding pet names again", "fix the voice profile", "tune ursula", "the profile is missing Y", "the voice keeps saying X", "adjust the ursula profile".
---

# Refine Voice Profile

Surgically edit the installed voice profile to add a guardrail, remove a misinterpretation, or tighten a section the user has flagged. This is for small, targeted adjustments — for a full retrain from fresh samples use `/ursula:train`.

## Inputs

The user describes a behavior they want changed. Common shapes:

- **Forbid** — "Stop using pet names like honey or sugar."
- **Remove** — "Get rid of the 'faintly sheepish' descriptor; that's a misread of my hedging."
- **Modify** — "The hedging characterization is too blanket — I don't hedge things I've verified."
- **Add** — "You missed that I always say 'for posterity' when cross-posting."

If the user invokes the skill with no detail, ask one clarifying question: *"What's the profile doing (or missing) that you want adjusted?"* Then proceed.

## Prerequisites

The installed profile must exist at `~/.claude/skills/ursula-voice/SKILL.md`. If it doesn't, stop and tell the user to run `/ursula:train` first — there is no profile to refine.

## Step 1: Drift check

Before reading, check that the installed and canonical copies are in sync:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sync-profile.sh" --check
```

- Exit `0` with `in-sync` → continue.
- Exit `0` with `canonical-missing` → continue; the sync at Step 6 will create it.
- Exit `2` with `drift` → surface the diff to the user and ask which copy is the source of truth before proceeding. The installed copy at `~/.claude/skills/ursula-voice/SKILL.md` is what Claude actually reads at session start, so default to treating it as canonical unless the user says otherwise.

## Step 2: Read the current profile

Read `~/.claude/skills/ursula-voice/SKILL.md` end to end. The whole document is the editing surface — never edit blindly based on the user's complaint without seeing the surrounding language.

## Step 3: Classify the refinement

Map the user's request to one (or more) of four shapes:

1. **Forbid** — add a prohibition to the `Avoided` line under `Lexical Fingerprint`.
2. **Remove** — delete an inaccurate descriptor or claim.
3. **Modify** — reword an existing characterization to add nuance.
4. **Add** — insert a new signature construction, register shift, or pattern.

A single user complaint can span multiple shapes (e.g., "no pet names" benefits from both a Forbid line in `Avoided` and a reinforcing rule in `Imitation Quick-Reference`). Handle them as one cohesive edit set per invocation.

## Step 4: Locate the right section

Map the refinement to the section(s) most likely to govern the behavior:

- Pet names, em-dashes, profanity, formal salutations → **Lexical Fingerprint → Avoided**
- Tone descriptors, register characterization → **Register & Tone**
- Hedging, intensifiers, stance markers → **Hedging, Intensifiers & Stance Markers**
- Recurring multi-word patterns → **Signature Constructions**
- Punctuation, capitalization, emoji habits → **Formatting Habits**
- Reply-vs-compose differences → **Voice in Conversational Reply vs Composed Composition**
- Cross-cutting imitation rules → **Imitation Quick-Reference**

For cross-cutting issues, expect to edit two sections in lockstep: the section that *defines* the rule, and `Imitation Quick-Reference` which *enforces* it.

## Step 5: Draft the edit

Draft each change as a precise old → new comparison. Constraints:

- Keep edits small and surgical. Do not rewrite whole sections.
- Match the existing profile's voice and structure so the refined text reads continuously.
- When adding a prohibition, briefly explain *why* the misinterpretation was likely (so a future reader sees the rationale, e.g., *"reading the warmth marker as folksy-Southern is a misinterpretation, not the register"*). This is what stops the model from re-inferring the forbidden behavior from adjacent descriptors.
- When removing a descriptor, only delete the descriptor itself — do not touch the surrounding sentence's structure.

## Step 6: Show the diff and get approval

Present the proposed edit(s) to the user as section-name plus before/after blocks. Briefly state the rationale for each. Then **wait for explicit approval before writing anything**. If the user wants tweaks, revise and re-show.

## Step 7: Apply

Once the user approves:

1. Apply each edit to `~/.claude/skills/ursula-voice/SKILL.md` using the `Edit` tool.
2. Sync the installed copy back to the canonical archival copy, logging a one-line refinement summary:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/sync-profile.sh" --summary "<short description of what changed>"
   ```

   Keep the summary terse (a single line) — it lands in `~/.ursula/refinements.log` for future debugging.

## Step 8: Report

Tell the user:

1. The change is applied to both the installed skill and the canonical archival copy.
2. It takes effect on the **next session start** (the current session's already-loaded `ursula-voice` content stays as-is until restart). For in-session testing, run `/clear` or start a fresh session.
3. To see refinement history: `cat ~/.ursula/refinements.log`.
4. To regenerate the profile from scratch: `/ursula:train`.

## Failure modes

- **No profile installed** → stop, point at `/ursula:train`.
- **Installed and canonical copies diverge** → surface the diff, ask which is canonical, do not auto-resolve.
- **User's complaint is too vague to locate a section** → ask for a verbatim example of the offending output, then classify from that. Don't guess.
- **Refinement conflicts with existing profile language** (e.g., user wants to add something the profile explicitly forbids) → surface the conflict and ask the user how to resolve before drafting the edit.
- **Sync script reports an unexpected exit** → stop. Do not leave the installed copy edited without the canonical copy synced — that creates drift the next refinement will have to resolve.
