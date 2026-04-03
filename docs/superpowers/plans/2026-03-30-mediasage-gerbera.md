# MediaSage für Gerbera — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mediasage (KI-Playlist-Generator) für Gerbera DLNA anpassen — Plex-Integration durch Gerbera JSON-API ersetzen, Ausgabe als M3U-Datei statt Plex-Playlist.

**Architecture:** Fork von mediasage; `plex_client.py` wird durch `gerbera_client.py` (Gerbera JSON-API) ersetzt; `library_cache.py` synct von Gerbera statt Plex; `generator.py` schreibt M3U-Dateien; neue `favorites.py` lädt Lieblings-Künstler/Alben aus YAML für LLM-Boost. LLM-Kern, Frontend und Recommender bleiben unverändert.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, httpx, rapidfuzz, pyyaml, pytest, pytest-asyncio

---

## Dateiübersicht

| Datei | Aktion | Verantwortung |
|---|---|---|
| `backend/gerbera_client.py` | Neu | Liest Tracks direkt aus Gerberas SQLite-Datenbank |
| `backend/favorites.py` | Neu | `favorites.yaml` laden, `is_favorite()` bereitstellen |
| `favorites.yaml` | Neu | Nutzerpflegbare Favoriten (Künstler, Alben) |
| `backend/library_cache.py` | Anpassen | Schema + Sync für Gerbera (play_count, file_path statt user_rating) |
| `backend/generator.py` | Anpassen | M3U schreiben statt Plex-Playlist; Favoriten-Boost im Prompt |
| `backend/config.py` | Anpassen | GERBERA_URL/USER/PASS, PLAYLIST_OUTPUT_DIR, FAVORITES_FILE, MIN_PLAY_COUNT |
| `backend/main.py` | Anpassen | Plex-Endpoints entfernen; Gerbera-Sync- und Favoriten-Endpoints |
| `config.example.yaml` | Anpassen | Neue Konfigfelder dokumentieren |
| `backend/plex_client.py` | Löschen | Wird durch gerbera_client.py ersetzt |
| `tests/test_gerbera_client.py` | Neu | Unit-Tests mit gemocktem HTTP |
| `tests/test_favorites.py` | Neu | Unit-Tests für YAML-Lader und is_favorite() |
| `tests/test_m3u_output.py` | Neu | Unit-Tests für M3U-Generierung |
| `tests/test_library_cache.py` | Anpassen | Schema- und Sync-Tests für Gerbera |

---

## Task 1: Repo forken und Gerbera JSON-API erkunden

**Files:**
- Read: `backend/plex_client.py`
- Read: `backend/library_cache.py`
- Read: `backend/generator.py`
- Read: `backend/config.py`

- [ ] **Schritt 1: Mediasage forken**

```bash
git clone https://github.com/ecwilsonaz/mediasage.git
cd mediasage
git remote rename origin upstream
```

- [ ] **Schritt 2: Abhängigkeiten installieren**

```bash
pip install -r requirements.txt
pip install pyyaml pytest pytest-asyncio
```

- [ ] **Schritt 3: Gerbera JSON-API erkunden**

Gerbera-Web-UI im Browser öffnen (z.B. `http://192.168.1.x:49152`), Browser-DevTools → Network-Tab → folgende Requests beobachten und Response-JSON dokumentieren:

1. Seite laden → Auth-Request: `GET /api?req=auth&action=get_sid`
   - Notiere: Antwortstruktur (Felder für Session-ID)
2. Einloggen → `POST /api?req=auth&action=login`
   - Notiere: Request-Parameter, Response
3. Musik-Ordner öffnen → `GET /api?req=items&...` oder `GET /api?req=containers&...`
   - Notiere: Alle Felder pro Item (insbesondere `res` für Dateipfad, `dc:title`, `upnp:artist`, `upnp:album`, `upnp:genre`, `dc:date`, `upnp:playbackCount` o.ä.)

> **Wichtig:** Notiere die exakten JSON-Feldnamen für: Titel, Künstler, Album, Genre, Jahr, Dateipfad, Playcount. Diese fließen direkt in Task 3 ein.

- [ ] **Schritt 4: plex_client.py lesen und Äquivalente verstehen**

Lies `backend/plex_client.py` komplett. Notiere:
- Wie wird die Bibliothek durchsucht? (Methodenname, Parameter)
- Wie wird `user_rating` abgerufen?
- Wie wird eine Playlist erstellt? (Methodenname)

- [ ] **Schritt 5: library_cache.py lesen**

Lies `backend/library_cache.py`. Notiere:
- Exakte Tabellen- und Spaltennamen im SQLite-Schema
- Name der Sync-Funktion und ihre Signatur
- Wie wird `is_live` ermittelt?

- [ ] **Schritt 6: generator.py lesen**

Lies `backend/generator.py`. Notiere:
- Wo wird die Playlist in Plex geschrieben? (Funktionsname, ca. Zeile)
- Wie wird der LLM-Prompt aufgebaut? (relevante Funktion)
- Wie sieht ein einzelner Track-Eintrag im Prompt aus?

- [ ] **Schritt 7: Commit (Repo-Setup)**

```bash
git add .
git commit -m "chore: fork mediasage as base for gerbera adaptation"
```

---

## Task 2: Konfiguration anpassen

**Files:**
- Modify: `backend/config.py`
- Modify: `config.example.yaml`

- [ ] **Schritt 1: config.py anpassen**

Öffne `backend/config.py`. Ersetze die Plex-Felder (`PLEX_URL`, `PLEX_TOKEN`) durch:

```python
# In der Config-Klasse oder dem Settings-Dict — folge dem bestehenden Muster in config.py:
GERBERA_DB_PATH: str = ""        # z.B. "/home/user/gerbera.db"
PLAYLIST_OUTPUT_DIR: str = ""    # Gerbera-überwachtes Verzeichnis
FAVORITES_FILE: str = "favorites.yaml"
MIN_PLAY_COUNT: int = 0          # 0 = kein Filter
```

Entferne alle Referenzen auf `PLEX_URL`, `PLEX_TOKEN`, `PLEX_LIBRARY_SECTION`.

- [ ] **Schritt 2: config.example.yaml aktualisieren**

```yaml
# Gerbera-Datenbank (direkt auf dem gleichen Rechner)
GERBERA_DB_PATH: "/home/user/gerbera.db"

# Playlist-Output
PLAYLIST_OUTPUT_DIR: "/media/music/playlists"

# Favoriten
FAVORITES_FILE: "favorites.yaml"

# Filter
MIN_PLAY_COUNT: 0    # 0 = alle Tracks; z.B. 3 = nur Tracks mit ≥ 3 Plays
```

- [ ] **Schritt 3: Commit**

```bash
git add backend/config.py config.example.yaml
git commit -m "feat: replace plex config with gerbera config fields"
```

---

## Task 3: `gerbera_client.py` — SQLite-Reader

**Files:**
- Create: `backend/gerbera_client.py`
- Create: `tests/test_gerbera_client.py`

Gerberas SQLite-Datenbank (`~/gerbera.db`) enthält alle Metadaten direkt:
- `mt_cds_object`: id, dc_title (Titel), location (Dateipfad)
- `mt_metadata`: Key-Value-Paare pro Track (`upnp:artist`, `upnp:album`, `upnp:genre`, `dc:date`)
- `grb_cds_resource`: duration ("MM:SS"), Dateigröße etc.
- `grb_playstatus`: playCount pro Track

- [ ] **Schritt 1: Tests schreiben (schlagen fehl)**

```python
# tests/test_gerbera_client.py
import sqlite3
import tempfile
import os
import pytest
from backend.gerbera_client import GerberaTrack, read_tracks


def _create_test_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE mt_cds_object (
            id INTEGER PRIMARY KEY,
            ref_id INTEGER DEFAULT NULL,
            parent_id INTEGER NOT NULL DEFAULT 0,
            upnp_class VARCHAR(80),
            dc_title VARCHAR(255),
            location TEXT
        );
        CREATE TABLE mt_metadata (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL,
            property_name VARCHAR(255) NOT NULL,
            property_value TEXT NOT NULL
        );
        CREATE TABLE grb_cds_resource (
            item_id INTEGER NOT NULL,
            res_id INTEGER NOT NULL,
            handlerType INTEGER NOT NULL DEFAULT 0,
            purpose INTEGER NOT NULL DEFAULT 0,
            duration VARCHAR(255),
            PRIMARY KEY(item_id, res_id)
        );
        CREATE TABLE grb_playstatus (
            "group" VARCHAR(255) NOT NULL,
            item_id INTEGER NOT NULL,
            playCount INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY("group", item_id)
        );
    """)
    # Insert one track
    conn.execute("""
        INSERT INTO mt_cds_object (id, ref_id, upnp_class, dc_title, location)
        VALUES (1, NULL, 'object.item.audioItem.musicTrack',
                'So What', '/music/miles_davis/kind_of_blue/01_so_what.flac')
    """)
    for name, value in [
        ("upnp:artist", "Miles Davis"),
        ("upnp:album", "Kind of Blue"),
        ("upnp:genre", "Jazz"),
        ("dc:date", "1959"),
    ]:
        conn.execute(
            "INSERT INTO mt_metadata (item_id, property_name, property_value) VALUES (1, ?, ?)",
            (name, value),
        )
    conn.execute(
        "INSERT INTO grb_cds_resource (item_id, res_id, handlerType, purpose, duration) VALUES (1, 0, 0, 0, '09:22')"
    )
    conn.execute(
        "INSERT INTO grb_playstatus (\"group\", item_id, playCount) VALUES ('default', 1, 7)"
    )
    conn.commit()
    conn.close()


def test_read_tracks_returns_correct_fields():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_test_db(db_path)
        tracks = read_tracks(db_path)
        assert len(tracks) == 1
        t = tracks[0]
        assert t.gerbera_id == 1
        assert t.title == "So What"
        assert t.artist == "Miles Davis"
        assert t.album == "Kind of Blue"
        assert t.genre == "Jazz"
        assert t.year == 1959
        assert t.file_path == "/music/miles_davis/kind_of_blue/01_so_what.flac"
        assert t.play_count == 7
        assert t.duration_ms == 562000
    finally:
        os.unlink(db_path)


def test_read_tracks_skips_virtual_refs():
    """Tracks mit ref_id (virtuelle Einträge) werden nicht zurückgegeben."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_test_db(db_path)
        conn = sqlite3.connect(db_path)
        # Füge virtuellen Eintrag ein (ref_id gesetzt)
        conn.execute("""
            INSERT INTO mt_cds_object (id, ref_id, upnp_class, dc_title, location)
            VALUES (2, 1, 'object.item.audioItem.musicTrack', 'So What (copy)', '/music/copy.flac')
        """)
        conn.commit()
        conn.close()
        tracks = read_tracks(db_path)
        assert len(tracks) == 1  # virtueller Eintrag nicht dabei
    finally:
        os.unlink(db_path)


def test_read_tracks_play_count_zero_when_unplayed():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_test_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM grb_playstatus")
        conn.commit()
        conn.close()
        tracks = read_tracks(db_path)
        assert tracks[0].play_count == 0
    finally:
        os.unlink(db_path)
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
cd /Users/dirk.lange/projects/music && python -m pytest tests/test_gerbera_client.py -v
```
Erwartet: `ImportError: cannot import name 'GerberaTrack'`

- [ ] **Schritt 3: `gerbera_client.py` implementieren**

```python
# backend/gerbera_client.py
import sqlite3
from dataclasses import dataclass


@dataclass
class GerberaTrack:
    gerbera_id: int
    title: str
    artist: str
    album: str
    genre: str
    year: int
    duration_ms: int
    file_path: str
    play_count: int


def _parse_duration_ms(duration_str: str) -> int:
    """'MM:SS' oder 'H:MM:SS' → Millisekunden"""
    if not duration_str:
        return 0
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = int(parts[0]), float(parts[1])
            return int((minutes * 60 + seconds) * 1000)
        elif len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
            return int((hours * 3600 + minutes * 60 + seconds) * 1000)
    except (ValueError, IndexError):
        pass
    return 0


def read_tracks(db_path: str) -> list[GerberaTrack]:
    """Liest alle Audio-Tracks aus Gerberas SQLite-Datenbank."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT
            o.id,
            o.dc_title,
            o.location,
            r.duration,
            COALESCE(SUM(ps.playCount), 0) AS play_count,
            MAX(CASE WHEN m.property_name = 'upnp:artist' THEN m.property_value END) AS artist,
            MAX(CASE WHEN m.property_name = 'upnp:album'  THEN m.property_value END) AS album,
            MAX(CASE WHEN m.property_name = 'upnp:genre'  THEN m.property_value END) AS genre,
            MAX(CASE WHEN m.property_name = 'dc:date'     THEN m.property_value END) AS year_str
        FROM mt_cds_object o
        LEFT JOIN mt_metadata       m  ON m.item_id  = o.id
        LEFT JOIN grb_cds_resource  r  ON r.item_id  = o.id AND r.res_id = 0
        LEFT JOIN grb_playstatus    ps ON ps.item_id = o.id
        WHERE o.upnp_class = 'object.item.audioItem.musicTrack'
          AND o.ref_id IS NULL
        GROUP BY o.id
    """)

    tracks = []
    for row in cursor.fetchall():
        year_str = row["year_str"] or "0"
        try:
            year = int(str(year_str)[:4])
        except (ValueError, TypeError):
            year = 0

        tracks.append(GerberaTrack(
            gerbera_id=row["id"],
            title=row["dc_title"] or "",
            artist=row["artist"] or "",
            album=row["album"] or "",
            genre=row["genre"] or "",
            year=year,
            duration_ms=_parse_duration_ms(row["duration"] or ""),
            file_path=row["location"] or "",
            play_count=int(row["play_count"]),
        ))
    conn.close()
    return tracks
```

- [ ] **Schritt 4: Tests ausführen — müssen bestehen**

```bash
cd /Users/dirk.lange/projects/music && python -m pytest tests/test_gerbera_client.py -v
```
Erwartet: 3 PASSED

- [ ] **Schritt 5: Commit**

```bash
cd /Users/dirk.lange/projects/music
git add backend/gerbera_client.py tests/test_gerbera_client.py
git commit -m "feat: add gerbera_client sqlite reader for track metadata"
```

---

## Task 5: `library_cache.py` anpassen

**Files:**
- Modify: `backend/library_cache.py`
- Create/Modify: `tests/test_library_cache.py`

- [ ] **Schritt 1: Tests schreiben**

```python
# tests/test_library_cache.py
import sqlite3
import pytest
import tempfile
import os
from backend.library_cache import init_db, sync_tracks, get_tracks
from backend.gerbera_client import GerberaTrack

def make_track(**kwargs) -> GerberaTrack:
    defaults = dict(
        gerbera_id="1", title="So What", artist="Miles Davis",
        album="Kind of Blue", genre="Jazz", year=1959,
        duration_ms=562000, file_path="/music/so_what.flac", play_count=5
    )
    defaults.update(kwargs)
    return GerberaTrack(**defaults)

def test_init_db_creates_schema():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        cursor = conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "title" in columns
        assert "artist" in columns
        assert "file_path" in columns
        assert "play_count" in columns
        assert "gerbera_id" in columns
        assert "user_rating" not in columns  # Plex-Feld entfernt
    finally:
        os.unlink(db_path)

def test_sync_tracks_inserts_records():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        tracks = [make_track(), make_track(gerbera_id="2", title="Blue in Green")]
        sync_tracks(conn, tracks)
        cursor = conn.execute("SELECT COUNT(*) FROM tracks")
        assert cursor.fetchone()[0] == 2
    finally:
        os.unlink(db_path)

def test_get_tracks_filter_by_genre():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id="1", genre="Jazz"),
            make_track(gerbera_id="2", genre="Rock"),
        ])
        results = get_tracks(conn, genres=["Jazz"])
        assert len(results) == 1
        assert results[0]["artist"] == "Miles Davis"
    finally:
        os.unlink(db_path)

def test_get_tracks_filter_by_min_play_count():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id="1", play_count=10),
            make_track(gerbera_id="2", play_count=1),
        ])
        results = get_tracks(conn, min_play_count=5)
        assert len(results) == 1
        assert results[0]["play_count"] == 10
    finally:
        os.unlink(db_path)
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_library_cache.py -v
```
Erwartet: ImportError oder fehlende Funktionen

- [ ] **Schritt 3: `library_cache.py` anpassen**

Öffne `backend/library_cache.py`. Ersetze das bestehende Schema und die Sync-Funktion:

```python
# backend/library_cache.py
import sqlite3
import re
from typing import Optional
from backend.gerbera_client import GerberaTrack
import json


IS_LIVE_PATTERN = re.compile(
    r"\b(live|concert|in concert|at |@|bootleg|unplugged)\b", re.IGNORECASE
)


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gerbera_id  TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            artist      TEXT NOT NULL,
            album       TEXT NOT NULL,
            genres      TEXT NOT NULL DEFAULT '[]',
            year        INTEGER,
            duration_ms INTEGER,
            file_path   TEXT NOT NULL,
            play_count  INTEGER DEFAULT 0,
            is_live     BOOLEAN DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artist  ON tracks(artist)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year    ON tracks(year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_live ON tracks(is_live)")
    conn.commit()
    return conn


def sync_tracks(conn: sqlite3.Connection, tracks: list[GerberaTrack]) -> None:
    rows = []
    for t in tracks:
        is_live = bool(IS_LIVE_PATTERN.search(t.title or ""))
        genres_json = json.dumps([t.genre] if t.genre else [])
        rows.append((
            t.gerbera_id, t.title, t.artist, t.album,
            genres_json, t.year, t.duration_ms,
            t.file_path, t.play_count, is_live,
        ))
    conn.executemany("""
        INSERT INTO tracks
            (gerbera_id, title, artist, album, genres, year,
             duration_ms, file_path, play_count, is_live)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(gerbera_id) DO UPDATE SET
            title=excluded.title, artist=excluded.artist,
            album=excluded.album, genres=excluded.genres,
            year=excluded.year, duration_ms=excluded.duration_ms,
            file_path=excluded.file_path,
            play_count=excluded.play_count, is_live=excluded.is_live
    """, rows)
    conn.commit()


def get_tracks(
    conn: sqlite3.Connection,
    genres: Optional[list[str]] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_play_count: int = 0,
    exclude_live: bool = False,
) -> list[dict]:
    query = "SELECT * FROM tracks WHERE 1=1"
    params: list = []

    if genres:
        placeholders = ",".join("?" * len(genres))
        # genres ist JSON-Array — einfaches LIKE reicht für einzelne Genres
        genre_clauses = " OR ".join(["genres LIKE ?"] * len(genres))
        query += f" AND ({genre_clauses})"
        params.extend([f'%"{g}"%' for g in genres])

    if min_year:
        query += " AND year >= ?"
        params.append(min_year)
    if max_year:
        query += " AND year <= ?"
        params.append(max_year)
    if min_play_count > 0:
        query += " AND play_count >= ?"
        params.append(min_play_count)
    if exclude_live:
        query += " AND is_live = 0"

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Schritt 4: Tests ausführen — müssen bestehen**

```bash
pytest tests/test_library_cache.py -v
```
Erwartet: alle PASSED

- [ ] **Schritt 5: Commit**

```bash
git add backend/library_cache.py tests/test_library_cache.py
git commit -m "feat: adapt library_cache for gerbera (play_count, file_path, no user_rating)"
```

---

## Task 6: `favorites.py` und `favorites.yaml`

**Files:**
- Create: `backend/favorites.py`
- Create: `favorites.yaml`
- Create: `tests/test_favorites.py`

- [ ] **Schritt 1: Test schreiben**

```python
# tests/test_favorites.py
import tempfile, os, pytest
from backend.favorites import load_favorites, is_favorite

SAMPLE_YAML = """
artists:
  - "Miles Davis"
  - "Nick Cave"
albums:
  - artist: "Tom Waits"
    album: "Rain Dogs"
"""

def test_is_favorite_artist():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        path = f.name
    try:
        favs = load_favorites(path)
        assert is_favorite(favs, artist="Miles Davis") is True
        assert is_favorite(favs, artist="miles davis") is True   # case-insensitive
        assert is_favorite(favs, artist="Bob Dylan") is False
    finally:
        os.unlink(path)

def test_is_favorite_album():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        path = f.name
    try:
        favs = load_favorites(path)
        assert is_favorite(favs, artist="Tom Waits", album="Rain Dogs") is True
        assert is_favorite(favs, artist="Tom Waits", album="Bone Machine") is False
    finally:
        os.unlink(path)

def test_missing_file_returns_empty():
    favs = load_favorites("/nonexistent/favorites.yaml")
    assert is_favorite(favs, artist="Anyone") is False
```

- [ ] **Schritt 2: Test ausführen — muss fehlschlagen**

```bash
pytest tests/test_favorites.py -v
```
Erwartet: ImportError

- [ ] **Schritt 3: `favorites.py` implementieren**

```python
# backend/favorites.py
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Favorites:
    artists: set[str] = field(default_factory=set)
    albums: set[tuple[str, str]] = field(default_factory=set)  # (artist_lower, album_lower)


def load_favorites(path: str) -> Favorites:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return Favorites()

    artists = {a.lower() for a in data.get("artists", [])}
    albums = {
        (entry["artist"].lower(), entry["album"].lower())
        for entry in data.get("albums", [])
    }
    return Favorites(artists=artists, albums=albums)


def is_favorite(favs: Favorites, artist: str, album: Optional[str] = None) -> bool:
    if artist.lower() in favs.artists:
        return True
    if album and (artist.lower(), album.lower()) in favs.albums:
        return True
    return False
```

- [ ] **Schritt 4: `favorites.yaml` Vorlage anlegen**

```yaml
# favorites.yaml — Lieblings-Künstler und Alben
# Tracks von diesen Künstlern/Alben werden im Playlist-Prompt bevorzugt.

artists:
  - "Miles Davis"
  - "Nick Cave & The Bad Seeds"

albums:
  - artist: "Tom Waits"
    album: "Rain Dogs"
  - artist: "PJ Harvey"
    album: "Stories from the City, Stories from the Sea"
```

- [ ] **Schritt 5: Tests ausführen — müssen bestehen**

```bash
pytest tests/test_favorites.py -v
```
Erwartet: alle PASSED

- [ ] **Schritt 6: Commit**

```bash
git add backend/favorites.py favorites.yaml tests/test_favorites.py
git commit -m "feat: add favorites loader (artists and albums from YAML)"
```

---

## Task 7: M3U-Output in `generator.py`

**Files:**
- Modify: `backend/generator.py`
- Create: `tests/test_m3u_output.py`

- [ ] **Schritt 1: Test schreiben**

```python
# tests/test_m3u_output.py
import tempfile, os, pytest
from backend.generator import write_m3u

def test_write_m3u_creates_file():
    tracks = [
        {"title": "So What", "artist": "Miles Davis",
         "duration_ms": 562000, "file_path": "/music/so_what.flac"},
        {"title": "The Mercy Seat", "artist": "Nick Cave",
         "duration_ms": 413000, "file_path": "/music/mercy_seat.mp3"},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_m3u(
            tracks=tracks,
            playlist_title="Melancholic Sunday",
            output_dir=tmpdir,
            date_str="2026-03-30",
        )
        assert os.path.exists(path)
        content = open(path).read()
        assert content.startswith("#EXTM3U")
        assert "#EXTINF:562,Miles Davis - So What" in content
        assert "/music/so_what.flac" in content
        assert "#EXTINF:413,Nick Cave - The Mercy Seat" in content
        assert "2026-03-30_Melancholic Sunday.m3u" in path

def test_write_m3u_sanitizes_filename():
    tracks = [{"title": "Track", "artist": "A", "duration_ms": 0, "file_path": "/f.mp3"}]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_m3u(
            tracks=tracks,
            playlist_title="My/Playlist:Test",
            output_dir=tmpdir,
            date_str="2026-03-30",
        )
        filename = os.path.basename(path)
        assert "/" not in filename
        assert ":" not in filename
```

- [ ] **Schritt 2: Test ausführen — muss fehlschlagen**

```bash
pytest tests/test_m3u_output.py -v
```
Erwartet: ImportError (`write_m3u` nicht definiert)

- [ ] **Schritt 3: `write_m3u` in `generator.py` hinzufügen**

Öffne `backend/generator.py`. Füge folgende Funktion hinzu (suche nach dem Abschnitt wo die Plex-Playlist erstellt wird — ersetze diesen Block):

```python
import re as _re
from pathlib import Path
from datetime import date

def write_m3u(
    tracks: list[dict],
    playlist_title: str,
    output_dir: str,
    date_str: str | None = None,
) -> str:
    """Schreibt eine Extended-M3U-Datei und gibt den Dateipfad zurück."""
    if date_str is None:
        date_str = date.today().isoformat()

    # Ungültige Zeichen aus Dateinamen entfernen
    safe_title = _re.sub(r'[<>:"/\\|?*]', "_", playlist_title)
    filename = f"{date_str}_{safe_title}.m3u"
    output_path = Path(output_dir) / filename

    lines = ["#EXTM3U"]
    for track in tracks:
        duration_sec = int(track.get("duration_ms", 0) / 1000)
        artist = track.get("artist", "")
        title = track.get("title", "")
        file_path = track.get("file_path", "")
        lines.append(f"#EXTINF:{duration_sec},{artist} - {title}")
        lines.append(file_path)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(output_path)
```

Suche anschließend im selben File nach dem Aufruf von `server.createPlaylist(...)` und ersetze ihn durch:

```python
playlist_path = write_m3u(
    tracks=selected_tracks,
    playlist_title=playlist_title,
    output_dir=config.PLAYLIST_OUTPUT_DIR,
)
```

*(Passe `selected_tracks` und `playlist_title` an die tatsächlichen Variablennamen in `generator.py` an, die du in Task 1 notiert hast.)*

- [ ] **Schritt 4: Tests ausführen — müssen bestehen**

```bash
pytest tests/test_m3u_output.py -v
```
Erwartet: alle PASSED

- [ ] **Schritt 5: Commit**

```bash
git add backend/generator.py tests/test_m3u_output.py
git commit -m "feat: write m3u files instead of plex playlist"
```

---

## Task 8: Favoriten-Boost im LLM-Prompt

**Files:**
- Modify: `backend/generator.py`

- [ ] **Schritt 1: Test schreiben**

```python
# Ergänze tests/test_m3u_output.py oder erstelle tests/test_generator_prompt.py

from backend.generator import build_track_prompt_entry
from backend.favorites import Favorites

def test_favorite_artist_gets_tag():
    favs = Favorites(artists={"miles davis"}, albums=set())
    entry = build_track_prompt_entry(
        track={"title": "So What", "artist": "Miles Davis", "album": "Kind of Blue",
               "genres": '["Jazz"]', "year": 1959, "play_count": 5},
        favs=favs,
    )
    assert "[FAVORITE]" in entry

def test_non_favorite_has_no_tag():
    favs = Favorites(artists=set(), albums=set())
    entry = build_track_prompt_entry(
        track={"title": "Track", "artist": "Unknown", "album": "Album",
               "genres": "[]", "year": 2000, "play_count": 0},
        favs=favs,
    )
    assert "[FAVORITE]" not in entry
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_generator_prompt.py -v
```
Erwartet: ImportError

- [ ] **Schritt 3: `build_track_prompt_entry` in `generator.py` implementieren**

Suche in `generator.py` den Abschnitt wo Tracks in den Prompt eingebaut werden (aus Task 1 bekannt). Extrahiere die Logik in eine eigene Funktion und ergänze den Favoriten-Tag:

```python
import json as _json
from backend.favorites import Favorites, is_favorite

def build_track_prompt_entry(track: dict, favs: Favorites) -> str:
    """Formatiert einen Track für den LLM-Prompt; fügt [FAVORITE] für bevorzugte Tracks ein."""
    genres = _json.loads(track.get("genres", "[]"))
    genre_str = ", ".join(genres) if genres else "unbekannt"
    fav_tag = " [FAVORITE]" if is_favorite(favs, track["artist"], track.get("album")) else ""
    return (
        f"{track['artist']} — {track['title']} "
        f"({track.get('album', '')}, {track.get('year', '?')}, "
        f"Genre: {genre_str}, Plays: {track.get('play_count', 0)}){fav_tag}"
    )
```

Ersetze die bisherige Track-Formatierung im Prompt-Builder durch Aufrufe dieser Funktion.

- [ ] **Schritt 4: Tests ausführen — müssen bestehen**

```bash
pytest tests/test_generator_prompt.py -v
```
Erwartet: alle PASSED

- [ ] **Schritt 5: Commit**

```bash
git add backend/generator.py tests/test_generator_prompt.py
git commit -m "feat: boost favorite artists/albums in llm prompt with [FAVORITE] tag"
```

---

## Task 9: `main.py` bereinigen

**Files:**
- Modify: `backend/main.py`
- Delete: `backend/plex_client.py`

- [ ] **Schritt 1: Plex-Imports entfernen**

Öffne `backend/main.py`. Entferne alle Imports und Verwendungen von:
- `plex_client`
- `PlexServer`, `PlayQueue`
- Alle Endpoints die Plex-Clients, Playback oder Plex-Auth betreffen

- [ ] **Schritt 2: Sicherstellen dass `get_tracks()` `min_play_count` aus Config bekommt**

Suche in `generator.py` den Aufruf von `get_tracks(...)` (oder dem Äquivalent aus der Plex-Version). Stelle sicher, dass `config.MIN_PLAY_COUNT` übergeben wird:

```python
tracks = get_tracks(conn, min_play_count=config.MIN_PLAY_COUNT, ...)
```

- [ ] **Schritt 3: Gerbera-Sync-Endpoint hinzufügen**

```python
from backend.gerbera_client import GerberaClient
from backend.library_cache import init_db, sync_tracks

@app.post("/api/library/sync")
async def trigger_sync():
    """Synchronisiert die lokale SQLite-Datenbank mit Gerbera."""
    client = GerberaClient(
        base_url=config.GERBERA_URL,
        username=config.GERBERA_USERNAME,
        password=config.GERBERA_PASSWORD,
    )
    await client.connect()
    tracks = await client.get_all_tracks()
    conn = init_db(config.DB_PATH)
    sync_tracks(conn, tracks)
    return {"status": "ok", "tracks_synced": len(tracks)}
```

- [ ] **Schritt 4: Favoriten-Endpoint hinzufügen**

```python
from backend.favorites import load_favorites

@app.get("/api/favorites")
def get_favorites():
    favs = load_favorites(config.FAVORITES_FILE)
    return {
        "artists": list(favs.artists),
        "albums": [{"artist": a, "album": b} for a, b in favs.albums],
    }
```

- [ ] **Schritt 5: `plex_client.py` löschen**

```bash
git rm backend/plex_client.py
```

- [ ] **Schritt 6: Gesamte Testsuite ausführen**

```bash
pytest tests/ -v
```
Erwartet: alle PASSED, keine ImportErrors

- [ ] **Schritt 7: Commit**

```bash
git add backend/main.py
git commit -m "feat: replace plex endpoints with gerbera sync and favorites endpoints"
```

---

## Task 10: End-to-End Smoke Test

**Files:**
- Read: `config.example.yaml`

- [ ] **Schritt 1: `config.user.yaml` anlegen**

```yaml
GERBERA_URL: "http://<deine-gerbera-ip>:49152"
GERBERA_USERNAME: ""
GERBERA_PASSWORD: ""
PLAYLIST_OUTPUT_DIR: "/tmp/test_playlists"
FAVORITES_FILE: "favorites.yaml"
MIN_PLAY_COUNT: 0
# LLM (eines von diesen):
ANTHROPIC_API_KEY: "..."
```

- [ ] **Schritt 2: App starten**

```bash
mkdir -p /tmp/test_playlists
uvicorn backend.main:app --reload --port 8000
```

- [ ] **Schritt 3: Library-Sync auslösen**

```bash
curl -X POST http://localhost:8000/api/library/sync
```
Erwartet: `{"status": "ok", "tracks_synced": <anzahl>}` mit mehr als 0 Tracks

- [ ] **Schritt 4: Playlist generieren**

Im Browser `http://localhost:8000` öffnen und eine Playlist beschreiben, z.B. "melancholischer Jazz zum Sonntagmorgen". Prüfen:
- Playlist-Titel und Track-Liste werden angezeigt
- In `/tmp/test_playlists/` liegt eine neue `.m3u`-Datei
- M3U-Datei enthält gültige absolute Dateipfade

- [ ] **Schritt 5: M3U in Gerbera prüfen**

Gerbera-Web-UI öffnen → Playlist-Verzeichnis sollte die neue M3U enthalten und die Tracks spielbar sein.

- [ ] **Schritt 6: Abschluss-Commit**

```bash
git add config.user.yaml.example favorites.yaml
git commit -m "chore: add example user config and favorites template"
```

---

## Bekannte Risiken

| Risiko | Mitigierung |
|---|---|
| Gerbera JSON-API Feldnamen weichen ab | Task 1: DevTools-Erkundung vor Implementierung |
| `upnp:playbackCount` nicht exponiert | Fallback: `play_count = 0` für alle Tracks; Filter deaktivieren |
| Absolute Dateipfade in M3U ungültig | App muss auf gleichem Rechner wie Gerbera laufen |
| Gerbera Auth-Mechanismus anders als erwartet | Task 3 Auth-Logik nach DevTools-Befund anpassen |
