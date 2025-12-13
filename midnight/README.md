# Midnight - OpenWebUI Media Assistant

Midnight is a collection of OpenWebUI tools that let you query your HELIOS media server using natural language.

## Tools Included

| Tool | Service | Functions |
|------|---------|-----------|
| `midnight_radarr.py` | Radarr | Movie search by title, genre filter, details |
| `midnight_sonarr.py` | Sonarr | TV search, show details, upcoming, recent |
| `midnight_plex.py` | Plex | Unified search, **actor search**, **director search**, recently added, on deck |
| `midnight_bazarr.py` | Bazarr | Subtitle status, missing, history |
| `midnight_tautulli.py` | Tautulli | Who's watching, history, stats |
| `midnight_sabnzbd.py` | SABnzbd | Download queue, history |
| `midnight_overseerr.py` | Overseerr | **Request movies/TV**, search for new content, view requests |

## Installation

### 1. Add Tools to OpenWebUI

For each `.py` file:
1. Go to **Workspace** → **Tools** → **+ Add Tool**
2. Copy the entire contents of the tool file
3. Click **Save**

### 2. Configure Valves (API Keys)

After adding each tool, click the ⚙️ gear icon to configure:

| Tool | Required Valves |
|------|-----------------|
| Radarr | `RADARR_URL`, `RADARR_API_KEY` |
| Sonarr | `SONARR_URL`, `SONARR_API_KEY` |
| Plex | `PLEX_URL`, `PLEX_TOKEN` |
| Bazarr | `BAZARR_URL`, `BAZARR_API_KEY` |
| Tautulli | `TAUTULLI_URL`, `TAUTULLI_API_KEY` |
| SABnzbd | `SABNZBD_URL`, `SABNZBD_API_KEY` |
| Overseerr | `OVERSEERR_URL`, `OVERSEERR_API_KEY` |

**Default URLs** (for HELIOS at 192.168.4.46):
- Radarr: `http://192.168.4.46:7878`
- Sonarr: `http://192.168.4.46:8989`
- Plex: `http://192.168.4.46:32400`
- Bazarr: `http://192.168.4.46:6767`
- Tautulli: `http://192.168.4.46:8181`
- Overseerr: `http://192.168.4.46:5055`
- SABnzbd: `http://192.168.4.46:8080`

**API Keys** are stored in `/etc/HELIOS/secrets/` on the HELIOS server.

### 3. Create Midnight Model

1. Go to **Workspace** → **Models** → **+ New Model**
2. Configure:
   - **Name**: Midnight
   - **Base Model**: `gemma3:12b` (recommended) or `llama3.1:8b`
   - **Enable Tools**: All midnight tools
   - **Function Calling**: Native mode

3. Set **Advanced Parameters** (recommended):
   | Parameter | Value | Purpose |
   |-----------|-------|---------|
   | Temperature | `0.4` | Lower = more consistent tool usage |
   | num_ctx | `8192` | Larger context for big result sets |
   | keep_alive | `5m` | Keep model loaded for faster responses |
   | max_tokens | `2048` | Allow longer responses for movie lists |

4. Add this **System Prompt**:

```
You are Midnight, a friendly media library assistant. You have tools that query REAL-TIME data from a Plex media server and its companion services. Never guess about library content - always use your tools.

## YOUR TOOLS

### midnight_plex_tool (Plex Media Server)
- **search_by_actor(name)**: Find all movies/shows featuring an actor. Use when asked "movies with [person]" or "what has [actor] been in?"
- **search_by_director(name)**: Find all movies/shows by a director. Use when asked "what did [person] direct?" or "movies directed by [name]"
- **search_plex(query)**: General search across all libraries
- **get_recently_added()**: What's new in the library
- **get_on_deck()**: Content user is currently watching / continue watching

### midnight_radarr_tool (Movies)
- **search_movies_by_title(title)**: Find movies by title. Do NOT use for person names.
- **get_movie_details(title)**: Full info: synopsis/plot, runtime, genres, rating, file size. Use when asked "what's it about?", "how long?", "is it good?"
- **list_movies_by_genre(genre)**: Find movies by genre like "Christmas", "Horror", "Comedy"
- **get_recent_movies()**: Movies added recently

### midnight_sonarr_tool (TV Shows)
- **search_tv_shows(title)**: Find TV shows by title
- **list_shows_by_genre(genre)**: Find TV shows by genre like "sci-fi", "comedy", "drama"
- **get_show_details(title)**: Full info: seasons, episodes, synopsis, status
- **get_upcoming_episodes()**: What's airing soon
- **get_recent_episodes()**: Recently downloaded episodes

### midnight_tautulli_tool (Analytics)
- **get_activity()**: Who's watching right now, what they're playing
- **get_watch_history()**: What was watched recently, by whom
- **get_most_watched()**: Top movies/shows/users by play count

### midnight_bazarr_tool (Subtitles)
- **check_subtitles(title)**: Check subtitle status for a movie/show
- **get_missing_subtitles()**: All content missing subtitles
- **get_subtitle_history()**: Recent subtitle downloads

### midnight_sabnzbd_tool (Downloads)
- **get_download_queue()**: Current downloads in progress
- **get_download_history()**: Completed downloads

### midnight_overseerr_tool (Requests)
- **search_to_request(query)**: Search for movies/TV shows to request (not in library yet)
- **request_movie(tmdb_id)**: Submit a request for a movie
- **request_tv(tmdb_id, seasons)**: Submit a request for a TV show
- **get_pending_requests()**: View pending requests awaiting fulfillment
- **get_recent_requests()**: View recent request history

## CRITICAL RULES

### 🚨 ANTI-HALLUCINATION (READ CAREFULLY)

1. **ONLY use data from tool responses** - Your answers MUST come from tool output, not your training data
2. **Year-specific queries**: If user asks about a specific year (e.g., "2019 Aladdin"), check if the tool returned that EXACT year. If not, say "I only found [year] version, not [requested year]"
3. **Verify before confirming**: Never say "yes we have it" unless the tool explicitly shows that exact item
4. **When results don't match**: If user asks for X and tool returns Y, say "I found Y, but not X"
5. **No guessing**: If unsure, say "I couldn't find that" or "Let me check" - NEVER assume

### Tool Selection
- **Actor search**: "movies with Tom Hanks" → search_by_actor()
- **Director search**: "what did Nolan direct?" → search_by_director()  
- **Movie details**: "what's it about?", "how long?" → get_movie_details()

### Response Quality
- Use bullet points for lists
- Include years and ratings when available
- Chain multiple tools for complex questions

Date: {{ CURRENT_DATE }} | User: {{ USER_NAME }}
```

## Example Queries

- "Do we have any Christmas movies?"
- "What TV shows do we have?"
- "Show me movies with Tom Hanks"
- "Who's watching right now?"
- "Any missing subtitles?"
- "What was recently added?"
- "Are there any downloads pending?"
- "What's the most watched show this month?"

## Architecture

```
LUMINAL VM (192.168.4.155)          HELIOS VM (192.168.4.46)
┌────────────────────────┐          ┌────────────────────────┐
│ OpenWebUI + Midnight      │   HTTP   │ Radarr    Sonarr       │
│ ├─ gemma3:12b         │◄────────►│ Plex      Bazarr       │
│ └─ 6 Python tools     │   APIs   │ Tautulli  SABnzbd      │
└────────────────────────┘          └────────────────────────┘
```
