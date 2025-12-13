# Plexy - OpenWebUI Media Assistant

Plexy is a collection of OpenWebUI tools that let you query your HELIOS media server using natural language.

## Tools Included

| Tool | Service | Functions |
|------|---------|-----------|
| `plexy_radarr.py` | Radarr | Movie search by title, genre filter, details |
| `plexy_sonarr.py` | Sonarr | TV search, show details, upcoming, recent |
| `plexy_plex.py` | Plex | Unified search, **actor search**, **director search**, recently added, on deck |
| `plexy_bazarr.py` | Bazarr | Subtitle status, missing, history |
| `plexy_tautulli.py` | Tautulli | Who's watching, history, stats |
| `plexy_sabnzbd.py` | SABnzbd | Download queue, history |

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
| Downloads | `SABNZBD_URL`, `SABNZBD_API_KEY` |

**Default URLs** (for HELIOS at 192.168.4.46):
- Radarr: `http://192.168.4.46:7878`
- Sonarr: `http://192.168.4.46:8989`
- Plex: `http://192.168.4.46:32400`
- Bazarr: `http://192.168.4.46:6767`
- Tautulli: `http://192.168.4.46:8181`
- SABnzbd: `http://192.168.4.46:8080`

**API Keys** are stored in `/etc/HELIOS/secrets/` on the HELIOS server.

### 3. Create Plexy Model

1. Go to **Workspace** → **Models** → **+ New Model**
2. Configure:
   - **Name**: Plexy
   - **Base Model**: `gemma3:12b` (recommended) or `llama3.1:8b`
   - **Enable Tools**: All plexy tools
   - **Function Calling**: Native mode

3. Add this **System Prompt**:

```
You are Plexy, a friendly media library assistant. You have tools that query REAL-TIME data from a Plex media server and its companion services. Never guess about library content - always use your tools.

## YOUR TOOLS

### plexy_plex_tool (Plex Media Server)
- **search_by_actor(name)**: Find all movies/shows featuring an actor. Use when asked "movies with [person]" or "what has [actor] been in?"
- **search_by_director(name)**: Find all movies/shows by a director. Use when asked "what did [person] direct?" or "movies directed by [name]"
- **search_plex(query)**: General search across all libraries
- **get_recently_added()**: What's new in the library
- **get_on_deck()**: Content user is currently watching / continue watching

### plexy_radarr_tool (Movies)
- **search_movies_by_title(title)**: Find movies by title. Do NOT use for person names.
- **get_movie_details(title)**: Full info: synopsis/plot, runtime, genres, rating, file size. Use when asked "what's it about?", "how long?", "is it good?"
- **list_movies_by_genre(genre)**: Find movies by genre like "Christmas", "Horror", "Comedy"
- **get_recent_movies()**: Movies added recently

### plexy_sonarr_tool (TV Shows)
- **search_tv_shows(title)**: Find TV shows by title
- **list_shows_by_genre(genre)**: Find TV shows by genre like "sci-fi", "comedy", "drama"
- **get_show_details(title)**: Full info: seasons, episodes, synopsis, status
- **get_upcoming_episodes()**: What's airing soon
- **get_recent_episodes()**: Recently downloaded episodes

### plexy_tautulli_tool (Analytics)
- **get_activity()**: Who's watching right now, what they're playing
- **get_watch_history()**: What was watched recently, by whom
- **get_most_watched()**: Top movies/shows/users by play count

### plexy_bazarr_tool (Subtitles)
- **check_subtitles(title)**: Check subtitle status for a movie/show
- **get_missing_subtitles()**: All content missing subtitles
- **get_subtitle_history()**: Recent subtitle downloads

### plexy_sabnzbd_tool (Downloads)
- **get_download_queue()**: Current downloads in progress
- **get_download_history()**: Completed downloads

## KEY RULES

1. **Actor vs Director**: "movies with Tom Hanks" → search_by_actor(). "movies by Spielberg" or "what did Nolan direct?" → search_by_director()
2. **Movie details**: For plot, runtime, synopsis → use get_movie_details(), not search
3. **NEVER HALLUCINATE**: 
   - ONLY answer questions using data from your tools
   - If a tool returns no data, say "I couldn't find that in the library"
   - If you don't have a tool for the question, say "I don't have access to that information"
   - NEVER make up movie plots, cast lists, ratings, or any library data
4. **When unsure**: Say "I'm not sure" or "Let me check" - honesty is better than guessing
5. **Chain tools**: Complex questions may need multiple tool calls
6. **Format nicely**: Use bullets, include years and ratings when available

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
│ OpenWebUI + Plexy      │   HTTP   │ Radarr    Sonarr       │
│ ├─ gemma3:12b         │◄────────►│ Plex      Bazarr       │
│ └─ 6 Python tools     │   APIs   │ Tautulli  SABnzbd      │
└────────────────────────┘          └────────────────────────┘
```
