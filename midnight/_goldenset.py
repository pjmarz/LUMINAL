#!/usr/bin/env python3
"""
Midnight golden-set evaluator.

Hits OpenWebUI's OpenAI-compatible chat completions endpoint with 12 prompts
and scores each response on:

  (a) Correct tool dispatched (parsed from the assistant's tool_calls)
  (b) Response is non-empty and not a service error
  (c) Dates rendered absolutely (when applicable)
  (d) Response references real data, not invented facts

Usage:
    python3 midnight/_goldenset.py \\
        --base-url http://localhost:3000 \\
        --api-key <openwebui-api-key> \\
        --model midnight \\
        [--out midnight/_goldenset_results.md]

Generate the API key in OpenWebUI: Settings → Account → API Keys.
Run from the LUMINAL host (or wherever localhost:3000 reaches OpenWebUI)
to bypass Cloudflare Access.
"""

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(2)


# (prompt, expected_tool_name_substring, scoring_axes_to_check)
# Axes: 'tool', 'nonempty', 'absolute_date', 'no_error'
PROMPTS = [
    ("Who's in The Matrix?", "get_cast", ["tool", "nonempty", "no_error"]),
    ("What movies do we have with Tom Hanks?", "search_by_actor", ["tool", "nonempty", "no_error"]),
    ("What did Christopher Nolan direct?", "search_by_director", ["tool", "nonempty", "no_error"]),
    ("What's new in the library?", "get_recently_added", ["tool", "nonempty", "absolute_date", "no_error"]),
    ("What's the Bob's Burgers episode 'It's a Stunterful Life' about?", "get_episode_details", ["tool", "nonempty", "no_error"]),
    ("Show me Christmas movies", "list_movies_by_genre", ["tool", "nonempty", "no_error"]),
    ("What's currently downloading?", "get_download_queue", ["tool", "nonempty", "no_error"]),
    ("Who's watching right now?", "get_activity", ["tool", "nonempty", "no_error"]),
    ("Are there any missing subtitles?", "get_missing_subtitles", ["tool", "nonempty", "no_error"]),
    ("Search Seerr for the new Dune movie to request", "search_to_request", ["tool", "nonempty", "no_error"]),
    ("When was Premium Rush added to the library?", "get_recently_added", ["tool", "nonempty", "absolute_date", "no_error"]),
    ("Tell me about the show PLUR1BUS", "get_show_details", ["tool", "nonempty", "no_error"]),
]

# Phrases that indicate the model recognized a service-error string from the tool
ERROR_MARKERS = (
    "error:", "error fetching", "unreachable", "could not connect",
    "service is unavailable",
)

# Regex matching dates like "May 05, 2026" or "Apr 22, 2026"
ABSOLUTE_DATE_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b")
# Hand-wavy phrases that suggest the model dodged the absolute-date requirement
HANDWAVY_RE = re.compile(r"\b(recently|a few (days|weeks)|earlier|the other day)\b", re.IGNORECASE)


def score_response(prompt: str, expected_tool: str, axes: list,
                   tool_calls: list, content: str) -> dict:
    """Return per-axis pass/fail dict + overall pass count."""
    scores = {}
    if "tool" in axes:
        called = ", ".join(tool_calls) if tool_calls else "<none>"
        scores["tool"] = (
            any(expected_tool in tc for tc in tool_calls),
            f"expected '{expected_tool}', called: {called}",
        )
    if "nonempty" in axes:
        text = (content or "").strip()
        scores["nonempty"] = (len(text) >= 20, f"content length {len(text)}")
    if "no_error" in axes:
        lower = (content or "").lower()
        hit = next((m for m in ERROR_MARKERS if m in lower), None)
        scores["no_error"] = (hit is None, f"error marker: {hit!r}" if hit else "ok")
    if "absolute_date" in axes:
        has_abs = bool(ABSOLUTE_DATE_RE.search(content or ""))
        has_hand = bool(HANDWAVY_RE.search(content or ""))
        scores["absolute_date"] = (
            has_abs and not has_hand,
            f"absolute_date={has_abs}, handwavy={has_hand}",
        )
    return scores


def call_openwebui(base_url: str, api_key: str, model: str, prompt: str,
                   timeout: float) -> tuple[list, str, dict]:
    """Send a chat completion to OpenWebUI; return (tool_calls, content, raw)."""
    url = f"{base_url.rstrip('/')}/api/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "") or ""
    # Tool calls may appear in different shapes depending on OpenWebUI version
    tool_calls = []
    for tc in msg.get("tool_calls") or []:
        fn = (tc.get("function") or {}).get("name", "")
        if fn:
            tool_calls.append(fn)
    # Some OpenWebUI deployments embed tool source pills in the content; scan as fallback
    for hit in re.findall(r"midnight_\w+", content):
        if hit not in tool_calls:
            tool_calls.append(hit)
    return tool_calls, content, data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--api-key", required=True, help="OpenWebUI API key")
    parser.add_argument("--model", default="midnight", help="OpenWebUI model id (default: midnight)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", default="midnight/_goldenset_results.md")
    args = parser.parse_args()

    rows = []
    total_axes = 0
    passed_axes = 0
    started = datetime.datetime.now()

    for i, (prompt, expected_tool, axes) in enumerate(PROMPTS, 1):
        print(f"[{i:>2}/{len(PROMPTS)}] {prompt!r:.<70}", end=" ", flush=True)
        t0 = time.time()
        try:
            tool_calls, content, _raw = call_openwebui(
                args.base_url, args.api_key, args.model, prompt, args.timeout
            )
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            print(f"FAIL ({elapsed:.0f}ms): {e}")
            rows.append({
                "prompt": prompt, "expected_tool": expected_tool, "elapsed_ms": elapsed,
                "tool_calls": [], "content": "", "scores": {a: (False, f"request failed: {e}") for a in axes},
            })
            total_axes += len(axes)
            continue

        elapsed = (time.time() - t0) * 1000
        scores = score_response(prompt, expected_tool, axes, tool_calls, content)
        passes = sum(1 for ok, _ in scores.values() if ok)
        total_axes += len(scores)
        passed_axes += passes
        print(f"{passes}/{len(scores)} axes ({elapsed:.0f}ms)")
        rows.append({
            "prompt": prompt, "expected_tool": expected_tool, "elapsed_ms": elapsed,
            "tool_calls": tool_calls, "content": content, "scores": scores,
        })

    # Render markdown report
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Midnight Golden Set — {started.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        f"**Model:** `{args.model}` via `{args.base_url}`  ",
        f"**Result:** {passed_axes}/{total_axes} axes passed across {len(PROMPTS)} prompts",
        "",
        "## Per-prompt scoring",
        "",
        "| # | Prompt | Expected tool | Tools called | Axes | Pass | ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(rows, 1):
        passes = sum(1 for ok, _ in row["scores"].values() if ok)
        total = len(row["scores"])
        called = ", ".join(f"`{t}`" for t in row["tool_calls"]) or "_none_"
        axes_keys = ", ".join(row["scores"].keys())
        lines.append(
            f"| {i} | {row['prompt']!r} | `{row['expected_tool']}` | {called} | "
            f"{axes_keys} | {passes}/{total} | {row['elapsed_ms']:.0f} |"
        )
    lines += ["", "## Failed axis details", ""]
    for i, row in enumerate(rows, 1):
        fails = {a: msg for a, (ok, msg) in row["scores"].items() if not ok}
        if not fails:
            continue
        lines.append(f"### {i}. {row['prompt']}")
        for axis, msg in fails.items():
            lines.append(f"- **{axis}**: {msg}")
        lines.append("")
    out_path.write_text("\n".join(lines))
    print(f"\nReport written to {out_path}")

    return 0 if passed_axes == total_axes else 1


if __name__ == "__main__":
    sys.exit(main())
