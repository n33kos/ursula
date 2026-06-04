#!/usr/bin/env python3
"""
Synthesize a voice profile from collected writing samples.

Uses `claude --print` for multi-pass LLM synthesis — no API key needed.

Usage:
    python3 scripts/synthesize-profile.py ~/.ursula/samples/slack/messages.json \\
        [--passes N] [--model MODEL] [--timeout SECONDS]
"""

import argparse
import datetime
import json
import random
import subprocess
import sys
import textwrap
from pathlib import Path


PROFILE_PATH = Path.home() / ".ursula" / "profile" / "SKILL.md"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Max samples per synthesis batch to stay within context limits
BATCH_SIZE = 120

# Cap on auto-passes — merging too many partials degrades quality
MAX_AUTO_PASSES = 10

# Per-sample length cap for synthesis prompt (truncate longer)
MAX_SAMPLE_LEN = 1200

# Timeout per claude --print call (seconds)
CLAUDE_TIMEOUT = 1200

# Skill frontmatter — the install step copies the body of the SKILL.md into
# ~/.claude/skills/ursula-voice/, where Claude Code auto-discovers it
SKILL_NAME = "ursula-voice"
SKILL_DESCRIPTION = (
    "Voice and prose-style profile of the user. Read this skill at the start of any "
    "session and adopt the user's voice as your DEFAULT writing register for everything "
    "you produce — not just text composed on the user's behalf (outbound messages, drafts, "
    "documentation, commit messages, PR descriptions) but also conversational replies you "
    "write directly to the user. Match the register, rhythm, vocabulary, signature "
    "constructions, and formatting tells described here whenever possible. The user can "
    "override per-message with explicit voice direction; honor the override for that "
    "message and return to the trained voice afterward."
)


def load_samples(input_path: Path) -> dict:
    return json.loads(input_path.read_text())


def load_template() -> str:
    template_path = TEMPLATE_DIR / "synthesis-prompt.md"
    return template_path.read_text()


def prep_samples(samples: list[dict]) -> list[dict]:
    """Dedup (by text), truncate overly long samples, drop empties."""
    seen = set()
    cleaned = []
    for s in samples:
        text = s.get("text", "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if len(text) > MAX_SAMPLE_LEN:
            text = text[:MAX_SAMPLE_LEN] + "... [truncated]"
        cleaned.append({
            "text": text,
            "source": s.get("source", "unknown"),
            "channel": s.get("channel"),
        })
    return cleaned


def batch_samples(samples: list[dict], batch_size: int = BATCH_SIZE) -> list[list[dict]]:
    if len(samples) <= batch_size:
        return [samples]
    random.seed(42)
    shuffled = list(samples)
    random.shuffle(shuffled)
    return [shuffled[i:i + batch_size] for i in range(0, len(shuffled), batch_size)]


def run_synthesis_pass(template: str, samples: list[dict], pass_label: str, model: str) -> str:
    """Run a single synthesis pass via claude --print."""
    sample_text = "\n\n---\n\n".join(
        f"[{s.get('source', 'unknown')}{' #' + s['channel'] if s.get('channel') else ''}]\n{s['text']}"
        for s in samples
    )

    system_prompt = template + (
        "\n\nIMPORTANT: Output a COMPLETE voice profile with all sections filled. "
        "Do NOT summarize what you would do — produce the full profile document. "
        "Each section must have specific, evidence-backed observations."
    )

    user_prompt = f"Here are the user's writing samples to analyze:\n\n{sample_text}"

    print(f"  Running {pass_label} ({len(samples)} samples)...", flush=True)

    try:
        result = subprocess.run(
            [
                "claude", "--print",
                "--model", model,
                "--system-prompt", system_prompt,
                "-p", user_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT on {pass_label}", file=sys.stderr, flush=True)
        return ""

    if result.returncode != 0:
        print(f"  Warning: {pass_label} returned code {result.returncode}", file=sys.stderr, flush=True)
        if result.stderr:
            print(f"  stderr: {result.stderr[:300]}", file=sys.stderr, flush=True)

    out = result.stdout.strip()
    print(f"  -> {len(out)} chars", flush=True)
    return out


def run_merge_pass(partials: list[str], metadata: dict, model: str) -> str:
    """Merge multiple partial profiles into one coherent profile."""
    system_prompt = textwrap.dedent(f"""\
        You are merging multiple partial voice profiles into a single coherent profile.

        Each partial was generated from a different batch of the same writer's samples.
        Combine them into one unified profile — deduplicate observations, strengthen
        patterns that appear across batches, resolve contradictions by favoring the
        more specific observation.

        Metadata:
        - Samples analyzed: {metadata['sample_count']}
        - Sources: {', '.join(metadata['sources'])}

        Rules:
        - Keep the same section structure as the inputs.
        - If an observation appears in multiple batches, mention that — increase confidence.
        - Mark observations that only appear in one batch with [low confidence].
        - Keep quoted excerpts ≤ 25 words. Strip identifying content.
        - Output the FULL merged profile — do NOT output a summary of the merge process.
        - Start with: # Voice Profile
        - Second line: > Auto-generated by ursula | {metadata['sample_count']} samples | sources: {', '.join(metadata['sources'])}
    """)

    user_prompt = "## Partial profiles\n\n"
    for i, p in enumerate(partials):
        user_prompt += f"### Batch {i + 1}\n\n{p}\n\n"

    print(f"  Running merge pass ({len(partials)} batches)...", flush=True)

    try:
        result = subprocess.run(
            [
                "claude", "--print",
                "--model", model,
                "--system-prompt", system_prompt,
                "-p", user_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print("  TIMEOUT on merge pass", file=sys.stderr, flush=True)
        return ""

    out = result.stdout.strip()
    print(f"  -> {len(out)} chars", flush=True)
    return out


def wrap_with_skill_frontmatter(body: str) -> str:
    """Wrap the synthesized profile body in YAML frontmatter so it's a valid skill."""
    frontmatter = textwrap.dedent(f"""\
        ---
        name: {SKILL_NAME}
        description: {SKILL_DESCRIPTION}
        ---

        """)
    # If the synthesizer already prepended frontmatter (it shouldn't, but just in case),
    # strip it before wrapping
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5:].lstrip()
    return frontmatter + body


def main():
    parser = argparse.ArgumentParser(description="Synthesize voice profile from samples")
    parser.add_argument("input", help="Path to samples JSON")
    parser.add_argument("--passes", type=int, default=0, help="Override pass count (0 = auto, cap %d)" % MAX_AUTO_PASSES)
    parser.add_argument("--model", default="sonnet", help="Claude model (default: sonnet)")
    parser.add_argument("--timeout", type=int, default=0, help="Per-call timeout in seconds (0 = default)")
    args = parser.parse_args()

    if args.timeout > 0:
        global CLAUDE_TIMEOUT
        CLAUDE_TIMEOUT = args.timeout

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    data = load_samples(input_path)
    samples = data.get("samples", [])
    sources = sorted({s.get("source", "unknown") for s in samples})

    print(f"Loaded {len(samples)} samples from {input_path}", flush=True)
    samples = prep_samples(samples)
    print(f"After dedup/truncation: {len(samples)} unique samples", flush=True)

    if not samples:
        print("Error: no samples to synthesize", file=sys.stderr)
        sys.exit(1)

    metadata = {"sample_count": len(samples), "sources": sources}

    # Remove any prior profile so a failed run doesn't leave stale output behind
    if PROFILE_PATH.exists():
        PROFILE_PATH.unlink()
        print("Removed prior profile", flush=True)

    template = load_template()
    batches = batch_samples(samples)
    num_passes = args.passes if args.passes > 0 else min(len(batches), MAX_AUTO_PASSES)
    print(f"Running {num_passes} synthesis pass(es)...", flush=True)

    partials = []
    for i, batch in enumerate(batches[:num_passes]):
        profile = run_synthesis_pass(template, batch, f"pass {i + 1}/{num_passes}", args.model)
        if profile:
            partials.append(profile)

    if not partials:
        print("Error: all synthesis passes failed", file=sys.stderr)
        sys.exit(1)

    if len(partials) > 1:
        body = run_merge_pass(partials, metadata, args.model)
    else:
        body = partials[0]

    if not body:
        print("Error: empty final profile", file=sys.stderr)
        sys.exit(1)

    # Ensure header — fall back if the model omitted it
    if not body.startswith("# "):
        body = (
            f"# Voice Profile\n\n"
            f"> Auto-generated by ursula on {datetime.date.today().isoformat()} "
            f"| {metadata['sample_count']} samples | sources: {', '.join(metadata['sources'])}\n\n"
            + body
        )

    final = wrap_with_skill_frontmatter(body)

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(final)
    print(f"\nProfile written to {PROFILE_PATH}", flush=True)
    print(f"  Lines: {len(final.splitlines())}", flush=True)


if __name__ == "__main__":
    main()
