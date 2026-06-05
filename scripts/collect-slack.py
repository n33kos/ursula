#!/usr/bin/env python3
"""
Normalize raw Slack MCP search responses into a clean voice-sample corpus.

The Slack MCP tools (e.g. slack_search_public_and_private) can only be invoked
from inside a Claude session, not a subprocess — so this script does NOT call
the MCP. Instead, the /ursula:train skill drives the MCP calls itself and dumps
each page of raw search results into ~/.ursula/samples/slack/raw/ as JSON.
This script then walks that raw/ directory, extracts message text, filters out
junk (bot replies, link-only messages, very short replies, automod, etc.), and
writes a single normalized samples file.

Usage:
    python3 scripts/collect-slack.py \\
        --raw-dir ~/.ursula/samples/slack/raw \\
        --output ~/.ursula/samples/slack/messages.json \\
        [--min-length 25] [--max-length 4000]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_RAW_DIR = Path.home() / ".ursula" / "samples" / "slack" / "raw"
DEFAULT_OUTPUT = Path.home() / ".ursula" / "samples" / "slack" / "messages.json"

# Drop very short messages — "lol", "yep", "thx" tell us almost nothing about voice
DEFAULT_MIN_LENGTH = 25

# Truncate very long messages — pasted logs, code dumps, etc.
DEFAULT_MAX_LENGTH = 4000

# Substrings that flag automated / non-voice content. If any match, drop the message.
JUNK_SUBSTRINGS = [
    "has joined the channel",
    "has left the channel",
    "set the channel topic",
    "pinned a message",
    "uploaded a file",
    "shared a file",
    "<!channel>",
    "<!here>",
    "<!everyone>",
]

# Message-level patterns — link-only, mention-only, emoji-only — that are voiceless
LINK_ONLY_RE = re.compile(r"^\s*<https?://[^>]+>\s*$")
MENTION_ONLY_RE = re.compile(r"^\s*(<@[A-Z0-9]+>\s*)+$")
EMOJI_ONLY_RE = re.compile(r"^\s*(:[a-z0-9_+\-]+:\s*)+$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Light cleanup — strip Slack-flavored noise that obscures the voice signal."""
    # Strip mention markers but keep readability: <@U123> -> @user
    text = re.sub(r"<@[A-Z0-9]+>", "@user", text)
    # Strip channel mentions: <#C123|name> -> #name
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
    # Unwrap inline link syntax: <https://x|label> -> label, <https://x> -> https://x
    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    # Unescape Slack's HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def is_voiceful(text: str) -> bool:
    """Return True if the message has enough voice signal to be worth analyzing."""
    if not text:
        return False
    if LINK_ONLY_RE.match(text):
        return False
    if MENTION_ONLY_RE.match(text):
        return False
    if EMOJI_ONLY_RE.match(text):
        return False
    for substr in JUNK_SUBSTRINGS:
        if substr in text:
            return False
    return True


# The Slack MCP's slack_search_public_and_private tool wraps its results in a
# markdown-formatted text blob under a top-level "results" string field rather
# than returning structured message objects. We detect that shape and parse it
# with the regex pair below before falling back to the generic tree walk.
SLACK_MD_RESULT_BLOCK_RE = re.compile(
    r"### Result \d+ of \d+\n(?P<body>.*?)(?=\n### Result \d+ of \d+|\n*$)",
    re.DOTALL,
)
SLACK_MD_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z_ ]+):\s*(?P<value>.*?)$", re.MULTILINE)


def _parse_slack_md_block(block: str) -> dict | None:
    """Parse a single '### Result N of M' block from the Slack MCP markdown response."""
    # Pull simple Key: value fields first
    fields = {}
    for m in SLACK_MD_FIELD_RE.finditer(block):
        key = m.group("key").strip().lower()
        if key == "text":
            # Stop — Text:'s value is multi-line and lives below
            break
        fields[key] = m.group("value").strip()

    # Text section is everything after the literal "Text:" up to the trailing "---"
    text_match = re.search(r"\nText:\s*\n(.*?)(?:\n---\s*$|\Z)", block, re.DOTALL)
    if not text_match:
        return None
    text = text_match.group(1).strip()
    if not text:
        return None

    channel_field = fields.get("channel", "")
    # "#channel-name (ID: C123)" or "DM (ID: D123)"
    channel = None
    cm = re.match(r"(#\S+|DM)\b", channel_field)
    if cm:
        channel = cm.group(1)

    permalink = None
    pm = re.search(r"Permalink:\s*\[link\]\((https?://[^)]+)\)", block)
    if pm:
        permalink = pm.group(1)

    return {
        "text": text,
        "channel": channel,
        "ts": fields.get("message_ts"),
        "permalink": permalink,
    }


def extract_messages_from_payload(payload, source_label: str) -> list[dict]:
    """
    Walk a raw MCP search response and yield message dicts.

    Slack search responses come in several shapes:
      - The Slack MCP wraps its messages in a markdown text blob under the
        "results" key with "### Result N of M" delimiters. We parse that shape
        explicitly.
      - Other tools or future versions may return structured JSON; the generic
        tree-walk below handles {"messages": [...]}, {"matches": [...]},
        top-level lists, etc.
    """
    out = []

    # Slack MCP markdown-blob shape — detect and parse explicitly
    md_blob = None
    if isinstance(payload, str) and "### Result " in payload:
        md_blob = payload
    elif isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, str) and "### Result " in results:
            md_blob = results
    if md_blob is not None:
        for m in SLACK_MD_RESULT_BLOCK_RE.finditer(md_blob):
            parsed = _parse_slack_md_block(m.group("body"))
            if parsed:
                parsed["source"] = source_label
                out.append(parsed)
        return out

    # Generic tree walk for structured payloads
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        text = node.get("text") or node.get("message_text")
        if isinstance(text, str) and text.strip():
            channel = None
            ch = node.get("channel")
            if isinstance(ch, dict):
                channel = ch.get("name") or ch.get("id")
            elif isinstance(ch, str):
                channel = ch

            out.append({
                "text": text,
                "channel": channel,
                "ts": node.get("ts") or node.get("timestamp"),
                "user": node.get("user"),
                "permalink": node.get("permalink"),
                "source": source_label,
            })

        for key in ("messages", "matches", "results", "items", "data"):
            if key in node:
                walk(node[key])

    walk(payload)
    return out


def normalize(raw_dir: Path, min_length: int, max_length: int) -> list[dict]:
    if not raw_dir.exists():
        print(f"Error: raw dir {raw_dir} not found", file=sys.stderr)
        sys.exit(1)

    files = sorted(raw_dir.glob("*.json"))
    if not files:
        print(f"Error: no *.json files in {raw_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {len(files)} raw response file(s) from {raw_dir}", flush=True)

    seen_hashes = set()
    collected = []

    for f in files:
        raw = f.read_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # Fall back to treating the file as a raw text payload — the Slack
            # MCP markdown blob can be archived this way without re-wrapping.
            payload = raw

        messages = extract_messages_from_payload(payload, source_label=f.stem)
        kept = 0
        for msg in messages:
            cleaned = clean_text(msg["text"])
            if len(cleaned) < min_length:
                continue
            if not is_voiceful(cleaned):
                continue
            if len(cleaned) > max_length:
                cleaned = cleaned[:max_length] + "... [truncated]"

            # Dedupe on text hash — Slack search will return the same message
            # under multiple queries
            h = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            collected.append({
                "text": cleaned,
                "channel": msg.get("channel"),
                "ts": msg.get("ts"),
                "permalink": msg.get("permalink"),
                "source": msg["source"],
            })
            kept += 1

        print(f"  {f.name}: {len(messages)} candidates -> {kept} kept", flush=True)

    return collected


def main():
    parser = argparse.ArgumentParser(description="Normalize raw Slack MCP responses into voice samples")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    args = parser.parse_args()

    raw_dir = args.raw_dir.expanduser()
    output_path = args.output.expanduser()

    samples = normalize(raw_dir, args.min_length, args.max_length)

    if not samples:
        print("Error: no usable samples after filtering", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "source": "slack",
        "sample_count": len(samples),
        "samples": samples,
    }, indent=2))

    total_chars = sum(len(s["text"]) for s in samples)
    print(f"\nWrote {len(samples)} samples ({total_chars:,} chars) to {output_path}", flush=True)


if __name__ == "__main__":
    main()
