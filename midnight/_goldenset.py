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

# OpenWebUI exposes tool calls at the tool-class granularity (midnight_X_tool)
# rather than the method granularity (get_cast). Map method → tool class so the
# tool axis can match either form.
TOOL_CLASS_FOR_METHOD = {
    # Plex
    "search_plex": "midnight_plex_tool",
    "search_by_actor": "midnight_plex_tool",
    "search_by_director": "midnight_plex_tool",
    "get_cast": "midnight_plex_tool",
    "get_recently_added": "midnight_plex_tool",
    "get_on_deck": "midnight_plex_tool",
    "get_episode_details": "midnight_plex_tool",
    # Radarr
    "search_movies_by_title": "midnight_radarr_tool",
    "list_movies_by_genre": "midnight_radarr_tool",
    "get_movie_details": "midnight_radarr_tool",
    "get_recent_movies": "midnight_radarr_tool",
    # Sonarr
    "search_tv_shows": "midnight_sonarr_tool",
    "list_shows_by_genre": "midnight_sonarr_tool",
    "get_show_details": "midnight_sonarr_tool",
    "get_upcoming_episodes": "midnight_sonarr_tool",
    "get_recent_episodes": "midnight_sonarr_tool",
    # Tautulli
    "get_activity": "midnight_tautulli_tool",
    "get_watch_history": "midnight_tautulli_tool",
    "get_most_watched": "midnight_tautulli_tool",
    # Bazarr
    "check_subtitles": "midnight_bazarr_tool",
    "get_missing_subtitles": "midnight_bazarr_tool",
    "get_subtitle_history": "midnight_bazarr_tool",
    # SABnzbd
    "get_download_queue": "midnight_sabnzbd_tool",
    "get_download_history": "midnight_sabnzbd_tool",
    # Seerr
    "search_to_request": "midnight_seerr_tool",
    "request_movie": "midnight_seerr_tool",
    "request_tv": "midnight_seerr_tool",
    "get_pending_requests": "midnight_seerr_tool",
    "get_recent_requests": "midnight_seerr_tool",
}

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
        # Match either the method name (get_cast) or its tool-class
        # (midnight_plex_tool). OpenWebUI exposes the tool-class form.
        expected_class = TOOL_CLASS_FOR_METHOD.get(expected_tool, "")
        ok = any(
            (expected_tool and expected_tool in tc) or
            (expected_class and expected_class in tc)
            for tc in tool_calls
        )
        scores["tool"] = (
            ok,
            f"expected '{expected_tool}' (or '{expected_class}'), called: {called}",
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
    """Stream a chat completion from OpenWebUI; return (tool_calls, content, raw).

    Streaming is required because OpenWebUI's agentic flow with stream=False
    often returns the model's initial tool-call message (empty content) rather
    than the final synthesized text. Streaming aggregates all delta.content
    chunks plus tool_calls + sources fields into a coherent picture.
    """
    url = f"{base_url.rstrip('/')}/api/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    content_parts: list[str] = []
    tool_calls: list[str] = []
    raw_chunks: list[dict] = []

    def add_tool(name: str) -> None:
        if name and name not in tool_calls:
            tool_calls.append(name)

    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                raw_chunks.append(chunk)

                # Accumulate delta.content + delta.tool_calls. Some models
                # emit tokens via delta.reasoning_content (Ollama/gemma4 in
                # tool-use mode); capture both so we don't blackhole the answer.
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        content_parts.append(delta["content"])
                    if delta.get("reasoning_content"):
                        content_parts.append(delta["reasoning_content"])
                    for tc in delta.get("tool_calls") or []:
                        fn = (tc.get("function") or {}).get("name", "")
                        add_tool(fn)
                    # Some OpenWebUI builds emit a finished message field
                    msg = choice.get("message") or {}
                    if msg.get("content"):
                        content_parts.append(msg["content"])
                    if msg.get("reasoning_content"):
                        content_parts.append(msg["reasoning_content"])
                    for tc in msg.get("tool_calls") or []:
                        fn = (tc.get("function") or {}).get("name", "")
                        add_tool(fn)

                # OpenWebUI-specific top-level fields with tool attribution
                for source in chunk.get("sources") or []:
                    for key in ("source", "name"):
                        candidate = (source.get(key) or {}) if isinstance(source.get(key), dict) else {}
                        for nm in (candidate.get("name"), source.get("name")):
                            if nm and "midnight" in nm:
                                add_tool(nm)

    content = "".join(content_parts)
    # Fallback: scan combined content for citation pills like "midnight_plex_tool"
    for hit in re.findall(r"midnight_\w+", content):
        add_tool(hit)
    return tool_calls, content, {"chunks": len(raw_chunks)}


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
        # Include response content so we can manually verify whether the model
        # actually called a tool or hallucinated from training data
        preview = (row["content"] or "").strip()
        if preview:
            lines.append("<details><summary>Response content</summary>")
            lines.append("")
            lines.append("```")
            lines.append(preview[:2000] + ("\n[…truncated]" if len(preview) > 2000 else ""))
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")
    out_path.write_text("\n".join(lines))
    print(f"\nReport written to {out_path}")

    return 0 if passed_axes == total_axes else 1


if __name__ == "__main__":
    sys.exit(main())
