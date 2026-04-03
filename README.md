# CrateMind

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GHCR](https://img.shields.io/badge/ghcr-langdar2%2Fcratemind-blue)](https://ghcr.io/langdar2/cratemind)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**AI-powered playlists and album recommendations for your self-hosted music library—using only music you actually own.**

CrateMind is a self-hosted web app that creates playlists and recommends albums by combining LLM intelligence with your local music library. It reads directly from [Gerbera's](https://gerbera.io) SQLite database and saves playlists as M3U files back into Gerbera's watched directory—no cloud accounts, no streaming services.

*Home Screen:*
![CrateMind Screenshot](docs/images/screenshot-home.png)

*Playlist Flow:*
![CrateMind Screenshot](docs/images/screenshot-playlist-start.png)

*Sample Generated Playlist:*
![CrateMind Screenshot](docs/images/screenshot-playlist.png)

*Album Flow:*
![CrateMind Screenshot](docs/images/screenshot-album-start.png)

*Album Recommendation Questions:*
![CrateMind Screenshot](docs/images/screenshot-album.png)

---

## Quick Start

```bash
docker run -d \
  --name cratemind \
  -p 5765:5765 \
  -e GERBERA_DB_PATH=/gerbera/gerbera.db \
  -e GERBERA_PLAYLIST_OUTPUT_DIR=/music/playlists \
  -e GEMINI_API_KEY=your-key \
  -v /path/to/gerbera.db:/gerbera/gerbera.db:ro \
  -v /path/to/playlists:/music/playlists \
  --restart unless-stopped \
  ghcr.io/langdar2/cratemind:latest
```

Open **http://localhost:5765** — a setup wizard walks you through pointing CrateMind at your Gerbera database and choosing an AI provider.

**Requirements:** Docker, a running [Gerbera](https://gerbera.io) DLNA server with a music library, and an API key from Google, Anthropic, or OpenAI (or a local model via Ollama).

---

## Contents

- [Why CrateMind?](#why-cratemind)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Development](#development)
- [API Reference](#api-reference)

---

## Why CrateMind?

**Self-hosted music fans have few good options for AI playlists.**

Generic tools like ChatGPT recommend from an infinite catalog with no awareness of what you actually own. The result is a list of tracks you may not have. CrateMind inverts the approach: it only ever sees your library, so every suggestion is guaranteed to exist on your machine.

| Other tools (ChatGPT, etc.) | CrateMind |
|-----------------------------|-----------|
| AI recommends from infinite catalog | AI only sees your library |
| Results may not exist locally | No missing tracks possible |
| Near-empty playlists | Full playlists, every time |

Playlists are written as M3U files directly into Gerbera's watched directory, so they appear immediately in any DLNA client on your network.

---

## Features

### Playlist Generation

Create playlists two ways:

**Describe what you want** — Natural language prompts like:
- "Melancholy 90s alternative for a rainy day"
- "Upbeat instrumental jazz for a dinner party"
- "Late night electronic, nothing too aggressive"

**Start from a song** — Pick a track you love, then explore musical dimensions: mood, era, instrumentation, genre, production style. Select which qualities you want more of.

### Album Recommendations

Describe a mood or moment, answer two quick questions about your preferences, and get a single perfect album to listen to—with an editorial pitch explaining why it fits.

- **Library mode** — recommends albums you already own
- **Discovery mode** — suggests albums you don't own yet, based on your taste profile
- **Familiarity control** — choose between comfort picks, hidden gems, or rediscoveries
- **Show Me Another** — regenerate without starting over
- Primary recommendation with a full write-up, plus two secondary picks

### Smart Filtering

Before the AI sees anything, you control the pool:
- **Genres** — Select from your library's actual genre tags
- **Decades** — Filter by era
- **Play count** — Only tracks you've listened to at least N times
- **Exclude live versions** — Skip concert recordings automatically

Real-time track counts show exactly how your filters narrow results.

### Direct Library Access

CrateMind reads your music library directly from Gerbera's SQLite database—no sync required, no Gerbera API calls. Track metadata (title, artist, album, genre, year, play count) is read from `gerbera.db` on startup and kept in a local cache for fast filtering.

- **Setup wizard** walks you through first-run configuration
- **Footer status** shows track count and last read time
- **Manual refresh** re-reads the database on demand

### Playlist Output

Generated playlists are written as Extended M3U files into Gerbera's playlist directory:

- Gerbera picks them up automatically and makes them available to all DLNA clients
- Filenames include the date for easy browsing
- Preview tracks before saving, remove ones you don't want, rename the playlist

### Multi-Provider Support

Bring your own API key—or run locally:

| Provider | Max Tracks | Typical Cost | Best For |
|----------|------------|--------------|----------|
| **Google Gemini** | ~18,000 | $0.03 – $0.25 | Large libraries, lowest cost |
| **Anthropic Claude** | ~3,500 | $0.15 – $0.25 | Nuanced recommendations |
| **OpenAI GPT** | ~2,300 | $0.05 – $0.10 | Solid all-around |
| **Ollama** ⚗️ | Varies | Free | Privacy, local inference |
| **Custom** ⚗️ | Configurable | Free | Self-hosted, OpenAI-compatible APIs |

⚗️ *Local LLM support is experimental. [Report issues](https://github.com/langdar2/cratemind/issues).*

> **Free option:** Google Gemini offers a free API tier that's more than enough for personal use — no credit card required. See the [Gemini free credit guide](docs/gemini-free-credit-guide.md) for setup instructions and details.

Estimated cost displays before you generate. CrateMind auto-detects your provider based on which key you configure.

---

## Installation

### Docker Compose (Recommended)

```bash
mkdir cratemind && cd cratemind
curl -O https://raw.githubusercontent.com/langdar2/cratemind/main/docker-compose.yml
```

Edit `docker-compose.yml` and set the environment variables and volume paths for your setup (see [Configuration](#configuration)).

Start:

```bash
docker compose up -d
```

### NAS Platforms

<details>
<summary><strong>Synology (Container Manager)</strong></summary>

**GUI:**
1. **Container Manager** → **Registry** → Search `ghcr.io/langdar2/cratemind`
2. Download `latest` tag
3. **Container** → **Create**
4. Port: 5765 → 5765
5. Add environment variables: `GERBERA_DB_PATH`, `GERBERA_PLAYLIST_OUTPUT_DIR`, `GEMINI_API_KEY`
6. Add volume mounts for your `gerbera.db` and playlist output directory

**Docker Compose:**
```bash
mkdir -p /volume1/docker/cratemind && cd /volume1/docker/cratemind
curl -O https://raw.githubusercontent.com/langdar2/cratemind/main/docker-compose.yml
nano docker-compose.yml  # set paths and API key
```
Then in **Container Manager** → **Project** → **Create**, point to `/volume1/docker/cratemind`.

**No Docker?** Some Synology models (especially ARM-based units) don't support Docker/Container Manager. See [Bare Metal](#bare-metal-no-docker) below for running CrateMind directly with Python.

</details>

<details>
<summary><strong>Unraid</strong></summary>

1. **Docker** → **Add Container**
2. Repository: `ghcr.io/langdar2/cratemind:latest`
3. Port: 5765 → 5765
4. Add variables: `GERBERA_DB_PATH`, `GERBERA_PLAYLIST_OUTPUT_DIR`, `GEMINI_API_KEY`
5. Add path mappings for your `gerbera.db` and playlist directory

</details>

<details>
<summary><strong>TrueNAS SCALE</strong></summary>

1. **Apps** → **Discover Apps** → **Custom App**
2. Image: `ghcr.io/langdar2/cratemind`, Tag: `latest`
3. Port: 5765
4. Add environment variables and storage paths

</details>

<details>
<summary><strong>Portainer</strong></summary>

**Stacks** → **Add Stack**:

```yaml
services:
  cratemind:
    image: ghcr.io/langdar2/cratemind:latest
    ports:
      - "5765:5765"
    environment:
      - GERBERA_DB_PATH=/gerbera/gerbera.db
      - GERBERA_PLAYLIST_OUTPUT_DIR=/music/playlists
      - GEMINI_API_KEY=your-key
    volumes:
      - /path/to/gerbera.db:/gerbera/gerbera.db:ro
      - /path/to/playlists:/music/playlists
      - ./data:/app/data
    restart: unless-stopped
```

</details>

### Bare Metal (No Docker)

Docker isn't required. CrateMind is Python + FastAPI with no native dependencies, so it runs on any machine with Python 3.11+ — including ARM-based Synology NAS models, Raspberry Pis, or any Linux/macOS/Windows box.

```bash
git clone https://github.com/langdar2/cratemind.git
cd cratemind
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set your environment variables:

```bash
export GERBERA_DB_PATH=/path/to/gerbera.db
export GERBERA_PLAYLIST_OUTPUT_DIR=/path/to/playlists
export GEMINI_API_KEY=your-gemini-key
```

Start the server:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 5765
```

Access at **http://your-machine-ip:5765**.

<details>
<summary><strong>Running as a background service (systemd)</strong></summary>

To keep CrateMind running after you close your terminal, create a systemd service:

```ini
# /etc/systemd/system/cratemind.service
[Unit]
Description=CrateMind
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/cratemind
EnvironmentFile=/path/to/cratemind/.env
ExecStart=/path/to/cratemind/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 5765
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cratemind
sudo systemctl start cratemind
```

</details>

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GERBERA_DB_PATH` | Yes | Path to your `gerbera.db` file (e.g. `/home/user/gerbera.db`) |
| `GERBERA_PLAYLIST_OUTPUT_DIR` | Yes | Directory where M3U playlists are written (must be watched by Gerbera) |
| `GERBERA_FAVORITES_FILE` | No | Favorites YAML file name (default: `favorites.yaml`) |
| `GERBERA_MIN_PLAY_COUNT` | No | Only include tracks with at least this many plays (default: `0` = all tracks) |
| `GEMINI_API_KEY` | One required | Google Gemini API key |
| `ANTHROPIC_API_KEY` | One required | Anthropic API key |
| `OPENAI_API_KEY` | One required | OpenAI API key |
| `LLM_PROVIDER` | No | Force provider: `gemini`, `anthropic`, `openai`, `ollama`, `custom` |
| `OLLAMA_URL` | No | Ollama server URL (default: `http://localhost:11434`) |
| `OLLAMA_CONTEXT_WINDOW` | No | Override detected context window for Ollama (default: 32768) |
| `CUSTOM_LLM_URL` | No | Custom OpenAI-compatible API base URL |
| `CUSTOM_LLM_API_KEY` | No | API key for custom provider (if required) |
| `CUSTOM_CONTEXT_WINDOW` | No | Context window size for custom provider (default: 32768) |

### Web UI Configuration

You can also configure CrateMind through the **Settings** page in the web UI. Settings entered there are saved to `config.user.yaml` and persist across restarts. Environment variables always take priority over UI-saved settings.

### Advanced: config.yaml

Mount a config file for full control:

```yaml
gerbera:
  db_path: "/home/user/gerbera.db"
  playlist_output_dir: "/media/music/playlists"
  favorites_file: "favorites.yaml"
  min_play_count: 0  # 0 = all tracks; e.g. 3 = only tracks with >= 3 plays

llm:
  provider: "gemini"
  model_analysis: "gemini-2.5-flash"
  model_generation: "gemini-2.5-flash"
  smart_generation: false  # true = use smarter model for both (higher quality, ~3-5x cost)

defaults:
  track_count: 25
```

### Model Selection

CrateMind uses a two-model strategy by default:

| Role | Purpose | Models Used |
|------|---------|-------------|
| **Analysis** | Interpret prompts, suggest filters, analyze seed tracks | claude-sonnet-4-5 / gpt-4.1 / gemini-2.5-flash |
| **Generation** | Select tracks from filtered list | claude-haiku-4-5 / gpt-4.1-mini / gemini-2.5-flash |

This balances quality with cost. Enable `smart_generation: true` to use the analysis model for everything.

### Local LLM Setup (Experimental)

Run CrateMind with local models for privacy and zero API costs.

<details>
<summary><strong>Ollama</strong></summary>

1. Install [Ollama](https://ollama.ai) and pull a model:
   ```bash
   ollama pull llama3:8b
   ```

2. Configure CrateMind via environment or Settings UI:
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_URL=http://localhost:11434
   ```

3. Select your model in Settings → the context window is auto-detected.

**Recommended models:** `llama3:8b`, `qwen3:8b`, `mistral` — models with 8K+ context work best.

</details>

<details>
<summary><strong>Custom OpenAI-Compatible API</strong></summary>

For LM Studio, text-generation-webui, vLLM, or any OpenAI-compatible server:

1. Start your server with an OpenAI-compatible endpoint

2. Configure in Settings:
   - **API Base URL:** `http://localhost:5000/v1`
   - **API Key:** If required by your server
   - **Model Name:** The model identifier
   - **Context Window:** Your model's context size

</details>

**Note:** Local models are slower and may produce less accurate results than cloud providers. A 10-minute timeout is used for generation. Models with larger context windows will support more tracks.

---

## How It Works

CrateMind uses a **filter-first architecture** designed for large libraries (50,000+ tracks):

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ANALYZE                                                      │
│     LLM interprets your prompt → suggests genre/decade filters   │
├─────────────────────────────────────────────────────────────────┤
│  2. FILTER                                                       │
│     Local library cache narrowed to matching tracks              │
│     "90s Alternative" → 2,000 tracks                             │
├─────────────────────────────────────────────────────────────────┤
│  3. SAMPLE                                                       │
│     If too large for context, randomly sample                    │
│     Fits within model's token limits                             │
├─────────────────────────────────────────────────────────────────┤
│  4. GENERATE                                                     │
│     Filtered track list + prompt sent to LLM                     │
│     LLM selects best matches from available tracks               │
├─────────────────────────────────────────────────────────────────┤
│  5. MATCH                                                        │
│     Fuzzy matching links LLM selections to library               │
│     Handles minor spelling/formatting differences                │
├─────────────────────────────────────────────────────────────────┤
│  6. SAVE                                                         │
│     M3U playlist written to Gerbera's watched directory          │
│     Appears instantly in all DLNA clients on your network        │
└─────────────────────────────────────────────────────────────────┘
```

The library data comes directly from Gerbera's SQLite database (`gerbera.db`), which CrateMind reads in read-only mode. No Gerbera API calls are needed—just direct file access.

---

## Development

### Local Setup

```bash
git clone https://github.com/langdar2/cratemind.git
cd cratemind
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export GERBERA_DB_PATH=/path/to/gerbera.db
export GERBERA_PLAYLIST_OUTPUT_DIR=/path/to/playlists
export GEMINI_API_KEY=your-key

uvicorn backend.main:app --reload --port 5765
```

### Testing

```bash
pytest tests/ -v
```

### Tech Stack

- **Backend:** Python 3.11+, FastAPI, rapidfuzz, httpx
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **Library source:** Gerbera SQLite database (read-only)
- **Playlist output:** Extended M3U files
- **LLM SDKs:** anthropic, openai, google-genai (+ Ollama via REST API)
- **Deployment:** Docker

---

## API Reference

Interactive documentation available at `/docs` when running.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/config` | GET/POST | Get or update configuration |
| `/api/setup/status` | GET | Onboarding checklist state |
| `/api/setup/validate-ai` | POST | Validate AI provider credentials |
| `/api/setup/complete` | POST | Mark setup wizard as complete |
| `/api/browse` | GET | Browse the filesystem (for path configuration) |
| `/api/library/status` | GET | Library state and track count |
| `/api/library/sync` | POST | Re-read library from Gerbera database |
| `/api/library/stats` | GET | Genre, decade, and artist statistics |
| `/api/library/stats/cached` | GET | Cached library statistics |
| `/api/library/search` | GET | Search library tracks |
| `/api/library/artists` | GET | List all artists |
| `/api/library/albums` | GET | List all albums |
| `/api/favorites/toggle` | POST | Mark/unmark a track as favourite |
| `/api/analyze/prompt` | POST | Analyze natural language prompt |
| `/api/analyze/track` | POST | Analyze a seed track |
| `/api/filter/preview` | POST | Preview filtered track list |
| `/api/generate/stream` | POST | Stream playlist generation (SSE) |
| `/api/generate/favorites` | POST | Generate a Favorites Mix playlist |
| `/api/playlist` | POST | Save playlist as M3U file |
| `/api/recommend/albums/preview` | GET | Preview album candidates for filters |
| `/api/recommend/analyze-prompt` | POST | Analyze prompt for genre/decade filters |
| `/api/recommend/questions` | POST | Generate clarifying questions |
| `/api/recommend/generate` | POST | Generate album recommendations |
| `/api/recommend/switch-mode` | POST | Switch library/discovery mode |
| `/api/results` | GET | List saved result history |
| `/api/results/{id}` | GET/DELETE | Get or delete a saved result |
| `/api/art/{rating_key}` | GET | Serve album art from local library |
| `/api/external-art` | GET | Fetch album art from external sources |
| `/api/ollama/status` | GET | Ollama connection status |
| `/api/ollama/models` | GET | List available Ollama models |
| `/api/ollama/model-info` | GET | Get model details (context window) |

---

## License

MIT
