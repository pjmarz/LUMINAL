# Midnight Golden Set — 2026-05-07 18:55 

**Model:** `midnight` via `http://localhost:3000`  
**Result:** 36/38 axes passed across 12 prompts

## Per-prompt scoring

| # | Prompt | Expected tool | Tools called | Axes | Pass | ms |
|---|---|---|---|---|---|---|
| 1 | "Who's in The Matrix?" | `get_cast` | `midnight_plex_tool` | tool, nonempty, no_error | 3/3 | 14177 |
| 2 | 'What movies do we have with Tom Hanks?' | `search_by_actor` | `midnight_plex_tool` | tool, nonempty, no_error | 3/3 | 12914 |
| 3 | 'What did Christopher Nolan direct?' | `search_by_director` | `midnight_plex_tool` | tool, nonempty, no_error | 3/3 | 10119 |
| 4 | "What's new in the library?" | `get_recently_added` | `midnight_plex_tool` | tool, nonempty, no_error, absolute_date | 3/4 | 21063 |
| 5 | "What's the Bob's Burgers episode 'It's a Stunterful Life' about?" | `get_episode_details` | `midnight_plex_tool:get_episode_details` | tool, nonempty, no_error | 3/3 | 15818 |
| 6 | 'Show me Christmas movies' | `list_movies_by_genre` | `midnight_radarr_tool` | tool, nonempty, no_error | 3/3 | 12463 |
| 7 | "What's currently downloading?" | `get_download_queue` | `midnight_plex_tool`, `midnight_radarr_tool`, `midnight_sonarr_tool`, `midnight_bazarr_tool`, `midnight_sabnzbd_tool`, `midnight_seerr_tool` | tool, nonempty, no_error | 3/3 | 41938 |
| 8 | "Who's watching right now?" | `get_activity` | `midnight_tautulli_tool` | tool, nonempty, no_error | 3/3 | 21177 |
| 9 | 'Are there any missing subtitles?' | `get_missing_subtitles` | `midnight_bazarr_tool` | tool, nonempty, no_error | 3/3 | 14126 |
| 10 | 'Search Seerr for the new Dune movie to request' | `search_to_request` | `midnight_seerr_tool` | tool, nonempty, no_error | 3/3 | 13850 |
| 11 | 'When was Premium Rush added to the library?' | `get_recently_added` | `midnight_plex_tool` | tool, nonempty, no_error, absolute_date | 3/4 | 38128 |
| 12 | 'Tell me about the show PLUR1BUS' | `get_show_details` | `midnight_sonarr_tool` | tool, nonempty, no_error | 3/3 | 21731 |

## Failed axis details

### 4. What's new in the library?
- **absolute_date**: absolute_date=False, handwavy=False

<details><summary>Response content</summary>

```
The user is asking "What's new in the library?".
The tool `get_recently_added(media_type)` is designed for this purpose.
Since the user did not specify a media type (movies, shows, episodes), I should use the default or call it with `media_type="all"` to give a comprehensive answer.

Plan:
1. Call `midnight_plex_tool.get_recently_added(media_type="all")`.
2. Present the results clearly to the user.
```

</details>

### 11. When was Premium Rush added to the library?
- **absolute_date**: absolute_date=True, handwavy=True

<details><summary>Response content</summary>

```
The user is asking for the addition date of a specific movie/show: "Premium Rush".
I need to use the `get_recently_added` tool. Since the user is asking about a specific title and its addition date, I should first try to find the content using a general search, but the `get_recently_added` tool is the most direct way to answer "When was X added?".

I will assume "Premium Rush" is a movie and use `get_recently_added` with `media_type="movies"`. If that doesn't work, I will use `search_plex("Premium Rush")` to confirm it exists and then check the general 'recently added' list or use the general search results if they include dates.

Let's start with `get_recently_added(media_type="movies")` to see if it's in the list, or if I need to search for it first. Since the query is very specific, I'll use `search_plex` first to confirm the title exists, and then if that fails, I'll use `get_recently_added` to check the list.

However, the prompt implies that `get_recently_added` is for "what's new". If the user asks about a specific title, the general search is usually better, but since the goal is the *date added*, I must rely on the tools.

Let's check the `search_plex` tool first, as it's the general search.

Tool call: `midnight_plex_tool.search_plex("Premium Rush")`
If the search returns the title, I will then check the general 'recently added' list or assume the search result provides the date.

If the search is insufficient, I will call `get_recently_added(media_type="movies")` and look for "Premium Rush" in the results.**Tool Call:** midnight_plex_tool.search_plex("Premium Rush")
**Tool Output:**
[
  {
    "title": "Premium Rush",
    "type": "movie",
    "year": 2012,
    "rating": "PG-13",
    "added_on": "Jun 15, 2023"
  }
]

Premium Rush was added to the library on **Jun 15, 2023**.
```

</details>
