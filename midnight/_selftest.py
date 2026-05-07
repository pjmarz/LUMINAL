#!/usr/bin/env python3
"""
Local validation for Midnight tools — anti-hallucination contract + pure functions.

Run: python3 midnight/_selftest.py

Validates:
1. Every public Tool method returns a visible error string when its backend is
   unreachable (Valve points at http://127.0.0.1:1). No silent empties.
2. _fuzzy_match returns expected matches for known inputs.
3. Seerr _lookup_title caches the second call.
4. Plex get_recently_added renders dates in the container's local TZ. Catches
   regressions where TZ propagation gets dropped (the kind of bug that makes
   chat dates drift by a day from what the Plex UI shows).
"""

import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

MIDNIGHT = Path(__file__).resolve().parent
UNREACHABLE = "http://127.0.0.1:1"


def load(file_name: str):
    """Load a midnight_*.py module by file path (avoids package init)."""
    path = MIDNIGHT / file_name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_tools(file_name: str, **valve_overrides):
    mod = load(file_name)
    tools = mod.Tools()
    for k, v in valve_overrides.items():
        setattr(tools.valves, k, v)
    return tools


PLEX_VALVES = {"PLEX_URL": UNREACHABLE, "PLEX_TOKEN": "x"}
RADARR_VALVES = {"RADARR_URL": UNREACHABLE, "RADARR_API_KEY": "x"}
SONARR_VALVES = {"SONARR_URL": UNREACHABLE, "SONARR_API_KEY": "x"}
TAUTULLI_VALVES = {"TAUTULLI_URL": UNREACHABLE, "TAUTULLI_API_KEY": "x"}
BAZARR_VALVES = {"BAZARR_URL": UNREACHABLE, "BAZARR_API_KEY": "x"}
SABNZBD_VALVES = {"SABNZBD_URL": UNREACHABLE, "SABNZBD_API_KEY": "x"}
SEERR_VALVES = {"SEERR_URL": UNREACHABLE, "SEERR_API_KEY": "x"}


# (file_name, method_name, args, valve_overrides, expected_substrings_lowercased)
CASES = [
    ("midnight_plex.py", "search_plex", ["matrix"], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "search_by_actor", ["Tom Hanks"], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "search_by_director", ["Nolan"], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "get_cast", ["Matrix"], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "get_recently_added", [], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "get_on_deck", [], PLEX_VALVES, ["error"]),
    ("midnight_plex.py", "get_episode_details", ["Ozymandias"], PLEX_VALVES, ["error"]),

    ("midnight_radarr.py", "search_movies_by_title", ["Inception"], RADARR_VALVES, ["radarr error"]),
    ("midnight_radarr.py", "list_movies_by_genre", ["Action"], RADARR_VALVES, ["radarr error"]),
    ("midnight_radarr.py", "get_movie_details", ["Inception"], RADARR_VALVES, ["radarr error"]),
    ("midnight_radarr.py", "get_recent_movies", [], RADARR_VALVES, ["radarr error"]),

    ("midnight_sonarr.py", "search_tv_shows", ["Breaking Bad"], SONARR_VALVES, ["sonarr error"]),
    ("midnight_sonarr.py", "list_shows_by_genre", ["Drama"], SONARR_VALVES, ["sonarr error"]),
    ("midnight_sonarr.py", "get_show_details", ["Breaking Bad"], SONARR_VALVES, ["sonarr error"]),
    ("midnight_sonarr.py", "get_upcoming_episodes", [], SONARR_VALVES, ["error"]),
    ("midnight_sonarr.py", "get_recent_episodes", [], SONARR_VALVES, ["error"]),

    ("midnight_tautulli.py", "get_activity", [], TAUTULLI_VALVES, ["error"]),
    ("midnight_tautulli.py", "get_watch_history", [], TAUTULLI_VALVES, ["error"]),
    ("midnight_tautulli.py", "get_most_watched", [], TAUTULLI_VALVES, ["error"]),

    ("midnight_bazarr.py", "check_subtitles", ["Inception"], BAZARR_VALVES, ["bazarr error"]),
    ("midnight_bazarr.py", "get_missing_subtitles", [], BAZARR_VALVES, ["bazarr error"]),
    ("midnight_bazarr.py", "get_subtitle_history", [], BAZARR_VALVES, ["error"]),

    ("midnight_sabnzbd.py", "get_download_queue", [], SABNZBD_VALVES, ["sabnzbd error"]),
    ("midnight_sabnzbd.py", "get_download_history", [], SABNZBD_VALVES, ["sabnzbd error"]),

    ("midnight_seerr.py", "search_to_request", ["Dune"], SEERR_VALVES, ["seerr error"]),
    ("midnight_seerr.py", "request_movie", [123], SEERR_VALVES, ["seerr error"]),
    ("midnight_seerr.py", "request_tv", [123], SEERR_VALVES, ["seerr error"]),
    ("midnight_seerr.py", "get_pending_requests", [], SEERR_VALVES, ["seerr error"]),
    ("midnight_seerr.py", "get_recent_requests", [], SEERR_VALVES, ["seerr error"]),
]


async def run_contract_tests():
    passed, failed, failures = 0, 0, []
    for file_name, method, args, valves, expected in CASES:
        tools = make_tools(file_name, **valves)
        try:
            result = await getattr(tools, method)(*args)
        except Exception as e:
            failures.append((file_name, method, f"RAISED: {e!r}"))
            failed += 1
            continue
        if not isinstance(result, str):
            failures.append((file_name, method, f"non-string return: {type(result).__name__}"))
            failed += 1
            continue
        result_lower = result.lower()
        if any(word in result_lower for word in expected):
            passed += 1
        else:
            preview = result[:140].replace("\n", " ")
            failures.append((file_name, method, f"no error keyword in: {preview!r}"))
            failed += 1
    return passed, failed, failures


def run_tz_test():
    """
    Verify Plex get_recently_added renders dates in the process's local TZ.

    Uses a timestamp 02:07 UTC on May 5, 2026 (= 22:07 EDT on May 4) — the
    exact day-boundary case that exposed the bug where the openwebui
    container ran in UTC and rendered dates a day later than Plex's UI.
    """
    failures = []
    test_ts = 1777946825  # 2026-05-05 02:07 UTC == 2026-05-04 22:07 EDT

    plex_mod = load("midnight_plex.py")

    fake_response = {
        "MediaContainer": {
            "Metadata": [
                {"type": "movie", "title": "TZ Test", "year": 2026, "addedAt": test_ts},
            ]
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    def fake_get(*_args, **_kwargs):
        return FakeResponse()

    original_tz = os.environ.get("TZ")

    def render_under_tz(tz: str) -> str:
        os.environ["TZ"] = tz
        time.tzset()
        # Patch the module's `requests` reference so our fake intercepts the call
        original_requests_get = plex_mod.requests.get
        plex_mod.requests.get = fake_get
        try:
            tools = plex_mod.Tools()
            tools.valves.PLEX_URL = "http://example.invalid"
            tools.valves.PLEX_TOKEN = "x"
            return asyncio.run(tools.get_recently_added(limit=1, media_type="all"))
        finally:
            plex_mod.requests.get = original_requests_get

    try:
        utc_output = render_under_tz("UTC")
        if "May 05, 2026" not in utc_output:
            failures.append(("TZ=UTC", f"expected 'May 05, 2026' in output: {utc_output!r}"))

        edt_output = render_under_tz("America/New_York")
        if "May 04, 2026" not in edt_output:
            failures.append(("TZ=America/New_York", f"expected 'May 04, 2026' in output: {edt_output!r}"))

        # Sanity: same timestamp must produce different rendered dates
        if utc_output == edt_output:
            failures.append(("TZ comparison", "UTC and America/New_York rendered the same string"))
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()

    return failures, 3


def run_pure_tests():
    failures = []
    plex = load("midnight_plex.py").Tools()

    # _fuzzy_match: substring match scores 1.0
    matches = plex._fuzzy_match("matrix", [("The Matrix", "d1"), ("Unrelated", "d2")])
    if not (len(matches) == 1 and matches[0][0] == "The Matrix" and matches[0][2] == 1.0):
        failures.append(("_fuzzy_match substring", f"got {matches}"))

    # _fuzzy_match: typo within threshold still matches
    matches = plex._fuzzy_match("Tom Hanx", [("Tom Hanks", "x"), ("Bob", "y")], threshold=0.6)
    if not (matches and matches[0][0] == "Tom Hanks"):
        failures.append(("_fuzzy_match typo", f"got {matches}"))

    # _fuzzy_match: nothing close returns empty
    matches = plex._fuzzy_match("xyz_unique", [("Tom Hanks", "x"), ("Bob", "y")], threshold=0.6)
    if matches:
        failures.append(("_fuzzy_match no-match", f"unexpected: {matches}"))

    # Seerr _lookup_title cache: second call for same key must skip HTTP
    seerr = load("midnight_seerr.py").Tools()
    call_count = {"n": 0}

    def fake(_endpoint, *_a, **_k):
        call_count["n"] += 1
        return {"title": "Cached Movie", "name": "Cached Show"}

    seerr._make_request = fake
    t1 = seerr._lookup_title("movie", 42)
    t2 = seerr._lookup_title("movie", 42)
    if t1 != "Cached Movie" or t2 != "Cached Movie":
        failures.append(("_lookup_title result", f"got {t1!r}, {t2!r}"))
    if call_count["n"] != 1:
        failures.append(("_lookup_title cache", f"HTTP called {call_count['n']}× for cached key"))

    return failures, 4


def main():
    print("=" * 72)
    print("MIDNIGHT LOCAL VALIDATION")
    print("=" * 72)

    print("\n[1/3] Anti-hallucination contract (Valves → http://127.0.0.1:1)")
    p, f, contract_failures = asyncio.run(run_contract_tests())
    print(f"      {p}/{p + f} methods returned visible error strings")
    for file_name, method, msg in contract_failures:
        print(f"      ✗ {file_name}::{method} — {msg}")

    print("\n[2/3] Pure-function logic")
    pure_failures, pure_total = run_pure_tests()
    print(f"      {pure_total - len(pure_failures)}/{pure_total} pure tests passed")
    for name, msg in pure_failures:
        print(f"      ✗ {name} — {msg}")

    print("\n[3/3] Timezone rendering (Plex addedAt under TZ=UTC vs TZ=America/New_York)")
    tz_failures, tz_total = run_tz_test()
    print(f"      {tz_total - len(tz_failures)}/{tz_total} TZ checks passed")
    for name, msg in tz_failures:
        print(f"      ✗ {name} — {msg}")

    total_failed = f + len(pure_failures) + len(tz_failures)
    print()
    print("=" * 72)
    if total_failed == 0:
        print(f"ALL {p + pure_total + tz_total} CHECKS PASSED")
        sys.exit(0)
    else:
        print(f"FAILURES: {total_failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
