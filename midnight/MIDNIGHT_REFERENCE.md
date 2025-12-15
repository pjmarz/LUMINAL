# Midnight Tool Reference Guide

> **IMPORTANT**: This document describes the ACTUAL data returned by Midnight tools. When answering user questions, ONLY use information from tool outputs—never guess or assume.

---

## 🔧 Available Tools

### 1. midnight_plex_tool

#### `get_recently_added(limit, media_type)`
Returns recently added content **with dates**.

**Parameters:**
- `limit` (int): Number of items to return (default: 15)
- `media_type` (str): Filter type
  - `"movies"` → Only movies
  - `"episodes"` → Only individual TV episodes
  - `"shows"` → All TV content (seasons + episodes)
  - `"all"` → Everything (default)

**Returns for each item:**
- Title
- Year (for movies)
- Show name, Season, Episode number (for episodes)
- **Added date** (e.g., "Dec 14, 2025")

**Example output:**
```
🎬 **Premium Rush** (2012) — added Dec 13, 2025
📺 **Landman** S02E05 - The Pirate Dinner — added Dec 14, 2025
```

> ⚠️ If user asks "when was X added?", call this tool and find the `added` date in the output.

---

#### `search_plex(query)`
Search across all libraries for movies/TV shows.

**Returns:** Title, year, rating for matching content.

---

#### `search_by_actor(actor_name)`
Find all content featuring an actor.

**Returns:** List of movies and TV shows with that actor, including year and rating.

---

#### `search_by_director(director_name)`
Find all content directed by someone.

**Returns:** List of movies/shows directed by that person.

---

#### `get_on_deck()`
Get content currently in progress (continue watching).

**Returns:** Title, progress (minutes watched / total).

---

### 2. midnight_radarr_tool

#### `search_movies_by_title(title)`
Search for movies by title.

**Returns:** Titles matching the search.

> ⚠️ Do NOT use for person names—use Plex actor/director search instead.

---

#### `get_movie_details(title)`
Get full movie details.

**Returns:**
- Synopsis/plot
- Runtime (minutes)
- Genres
- Rating
- File size
- Resolution/quality

---

#### `list_movies_by_genre(genre)`
Find movies by genre.

**Supported genres:** Action, Comedy, Drama, Horror, Sci-Fi, Christmas, etc.

---

#### `get_recent_movies()`
Shows Radarr's download history.

> ⚠️ This shows **download dates**, NOT when added to Plex. For "recently added", use `get_recently_added(media_type="movies")`.

---

### 3. midnight_sonarr_tool

#### `search_tv_shows(title)`
Search for TV shows.

---

#### `get_show_details(title)`
Full TV show info.

**Returns:** Seasons, episodes, synopsis, air status.

---

#### `list_shows_by_genre(genre)`
Find shows by genre.

---

#### `get_upcoming_episodes()`
Episodes airing soon.

---

#### `get_recent_episodes()`
Shows Sonarr's download history.

> ⚠️ This shows **download dates**. For "recently added episodes", use `get_recently_added(media_type="episodes")`.

---

### 4. midnight_tautulli_tool

#### `get_activity()`
Who's watching right now.

**Returns:** Current streams, user, content being played.

---

#### `get_watch_history()`
What was watched recently.

**Returns:** Play history with user, title, and watch date.

---

#### `get_most_watched()`
Top content by play count.

---

### 5. midnight_bazarr_tool

#### `check_subtitles(title)`
Subtitle status for a movie/show.

---

#### `get_missing_subtitles()`
Content missing subtitles.

---

#### `get_subtitle_history()`
Recent subtitle downloads.

---

### 6. midnight_sabnzbd_tool

#### `get_download_queue()`
Current downloads in progress.

---

#### `get_download_history()`
Completed downloads.

---

### 7. midnight_overseerr_tool

#### `search_to_request(query)`
Search for content to request (not in library).

---

#### `request_movie(tmdb_id)`
Submit a movie request.

---

#### `request_tv(tmdb_id, seasons)`
Submit a TV show request.

---

#### `get_pending_requests()`
View pending requests.

---

#### `get_recent_requests()`
View recent request history.

---

## 🚨 Critical Anti-Hallucination Rules

1. **NEVER guess dates** — If asked "when was X added?", call `get_recently_added()` and read the actual date.

2. **NEVER invent data** — If a tool doesn't return specific info, say "I don't have that information."

3. **Re-call tools for follow-ups** — Don't rely on memory. Call tools again to verify.

4. **Trust tool output over training data** — Your training data about movies/shows is likely outdated. Always use tool results.

5. **Plex is the source of truth for "recently added"** — Radarr/Sonarr show download dates, not library addition dates.
