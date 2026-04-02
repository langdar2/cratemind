# Favorites UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace YAML-based favorites with a SQLite-backed Library browser where users heart artists/albums directly in the UI.

**Architecture:** New `favorites` table in `library_cache.db`; `library_cache.py` gets three new query functions; `favorites.py` reads from DB instead of YAML; two new GET endpoints + one POST endpoint; new `view-library` frontend tab with artist/album cards and heart toggles.

**Tech Stack:** Python 3.11, FastAPI, SQLite (sqlite3 stdlib), Pydantic, Vanilla JS ES6+

---

## File Map

| File | Change |
|---|---|
| `backend/library_cache.py` | Add `favorites` table to `init_schema()`; add `toggle_favorite()`, `get_artists_with_stats()`, `get_albums_with_stats()` |
| `backend/favorites.py` | Replace YAML `load_favorites(path)` with DB-backed `load_favorites()` (no path arg) |
| `backend/generator.py` | Remove `path` arg from both `load_favorites()` calls (lines 334, 580) |
| `backend/models.py` | Add `ToggleFavoriteRequest`, `ArtistStat`, `AlbumStat`, `LibraryArtistsResponse`, `LibraryAlbumsResponse` |
| `backend/main.py` | Remove `GET /api/favorites`; add `GET /api/library/artists`, `GET /api/library/albums`, `POST /api/favorites/toggle` |
| `tests/test_library_cache.py` | Add tests for `toggle_favorite`, `get_artists_with_stats`, `get_albums_with_stats` |
| `tests/test_favorites.py` | Replace YAML-based tests with DB-based tests for new `load_favorites()` |
| `frontend/index.html` | Add Library nav button; add `<div id="view-library">` with full HTML structure |
| `frontend/style.css` | Add styles for library cards, heart button, NEU badge, toggle switches |
| `frontend/app.js` | Add `state.library`; add `loadLibraryView()`, `renderLibrary()`, heart toggle handler |

---

## Task 1: Add `favorites` table to DB schema

**Files:**
- Modify: `backend/library_cache.py` (inside `init_schema()`, the `executescript` block at line ~213)
- Test: `tests/test_library_cache.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_library_cache.py`:

```python
def test_init_db_creates_favorites_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        cursor = conn.execute("PRAGMA table_info(favorites)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "type" in columns
        assert "artist" in columns
        assert "album" in columns
        assert "created_at" in columns
    finally:
        conn.close()
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_library_cache.py::test_init_db_creates_favorites_table -v
```

Expected: FAIL — `favorites` table has no columns (doesn't exist).

- [ ] **Step 3: Add `favorites` table to `init_schema()` executescript block**

In `backend/library_cache.py`, inside the `conn.executescript("""...""")` block in `init_schema()`, add after the `results` table definition (before the closing `"""`):

```sql
        -- Favorites: user-marked favorite artists and albums
        CREATE TABLE IF NOT EXISTS favorites (
            type       TEXT NOT NULL,
            artist     TEXT NOT NULL,
            album      TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );

        CREATE INDEX IF NOT EXISTS idx_favorites_artist ON favorites(artist);
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_library_cache.py::test_init_db_creates_favorites_table -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/test_library_cache.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/library_cache.py tests/test_library_cache.py
git commit -m "feat: add favorites table to library_cache schema"
```

---

## Task 2: Add `toggle_favorite()` to `library_cache.py`

**Files:**
- Modify: `backend/library_cache.py`
- Test: `tests/test_library_cache.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_library_cache.py`. Note: this test uses `init_db` (standalone), so add a helper to also create the `favorites` table:

```python
def make_db_with_favorites():
    """Create a temp DB with both tracks and favorites tables."""
    import tempfile, os
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gerbera_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL, artist TEXT, album TEXT,
            genres TEXT, year INTEGER, duration_ms INTEGER,
            file_path TEXT, play_count INTEGER DEFAULT 0,
            is_live BOOLEAN DEFAULT 0,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS favorites (
            type TEXT NOT NULL, artist TEXT NOT NULL,
            album TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );
    """)
    conn.commit()
    return conn, db_path


def test_toggle_favorite_insert_then_remove():
    from backend.library_cache import toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        # First toggle: inserts → returns True
        result = toggle_favorite("artist", "Radiohead", conn=conn)
        assert result is True
        row = conn.execute("SELECT * FROM favorites WHERE artist='Radiohead'").fetchone()
        assert row is not None

        # Second toggle: removes → returns False
        result = toggle_favorite("artist", "Radiohead", conn=conn)
        assert result is False
        row = conn.execute("SELECT * FROM favorites WHERE artist='Radiohead'").fetchone()
        assert row is None
    finally:
        conn.close()
        os.unlink(db_path)


def test_toggle_favorite_album():
    from backend.library_cache import toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        result = toggle_favorite("album", "Radiohead", album="OK Computer", conn=conn)
        assert result is True
        row = conn.execute(
            "SELECT * FROM favorites WHERE artist='Radiohead' AND album='OK Computer'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()
        os.unlink(db_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_library_cache.py::test_toggle_favorite_insert_then_remove tests/test_library_cache.py::test_toggle_favorite_album -v
```

Expected: FAIL — `toggle_favorite` not defined.

- [ ] **Step 3: Implement `toggle_favorite()`**

Add to `backend/library_cache.py` (after `get_cached_genre_decade_stats`):

```python
def toggle_favorite(
    fav_type: str,
    artist: str,
    album: str = "",
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Toggle a favorite on/off. Returns True if now a favorite, False if removed.

    Args:
        fav_type: 'artist' or 'album'
        artist: Artist name (stored as-is, matched case-insensitively elsewhere)
        album: Album name; empty string for artist-level favorites
        conn: Optional connection (used in tests); opens one if not provided
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        existing = conn.execute(
            "SELECT 1 FROM favorites WHERE type=? AND artist=? AND album=?",
            (fav_type, artist, album),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM favorites WHERE type=? AND artist=? AND album=?",
                (fav_type, artist, album),
            )
            conn.commit()
            return False
        else:
            conn.execute(
                "INSERT INTO favorites (type, artist, album) VALUES (?, ?, ?)",
                (fav_type, artist, album),
            )
            conn.commit()
            return True
    finally:
        if close_after:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_library_cache.py::test_toggle_favorite_insert_then_remove tests/test_library_cache.py::test_toggle_favorite_album -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/library_cache.py tests/test_library_cache.py
git commit -m "feat: add toggle_favorite() to library_cache"
```

---

## Task 3: Add `get_artists_with_stats()` and `get_albums_with_stats()`

**Files:**
- Modify: `backend/library_cache.py`
- Test: `tests/test_library_cache.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_library_cache.py`:

```python
def test_get_artists_with_stats_returns_sorted_by_track_count():
    from backend.library_cache import get_artists_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        # Insert tracks: Miles Davis 3 tracks, Radiohead 1 track
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (?,?,?,?,?,?,?)",
            [
                (1, "So What", "Miles Davis", "Kind of Blue", "[]", "/a.flac", 0),
                (2, "All Blues", "Miles Davis", "Kind of Blue", "[]", "/b.flac", 0),
                (3, "Blue in Green", "Miles Davis", "Kind of Blue", "[]", "/c.flac", 0),
                (4, "Creep", "Radiohead", "Pablo Honey", "[]", "/d.flac", 0),
            ],
        )
        conn.commit()
        rows = get_artists_with_stats(conn=conn)
        assert rows[0]["artist"] == "Miles Davis"
        assert rows[0]["track_count"] == 3
        assert rows[1]["artist"] == "Radiohead"
        assert rows[1]["track_count"] == 1
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_artists_with_stats_is_favorite_flag():
    from backend.library_cache import get_artists_with_stats, toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        conn.execute(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (1,'Creep','Radiohead','Pablo Honey','[]','/d.flac',0)"
        )
        conn.commit()
        toggle_favorite("artist", "Radiohead", conn=conn)
        rows = get_artists_with_stats(conn=conn)
        assert rows[0]["is_favorite"] is True
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_albums_with_stats_returns_sorted_by_track_count():
    from backend.library_cache import get_albums_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (?,?,?,?,?,?,?)",
            [
                (1, "Track1", "Radiohead", "OK Computer", "[]", "/a.flac", 0),
                (2, "Track2", "Radiohead", "OK Computer", "[]", "/b.flac", 0),
                (3, "Creep",  "Radiohead", "Pablo Honey", "[]", "/c.flac", 0),
            ],
        )
        conn.commit()
        rows = get_albums_with_stats(conn=conn)
        assert rows[0]["album"] == "OK Computer"
        assert rows[0]["track_count"] == 2
        assert rows[1]["album"] == "Pablo Honey"
    finally:
        conn.close()
        os.unlink(db_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_library_cache.py::test_get_artists_with_stats_returns_sorted_by_track_count tests/test_library_cache.py::test_get_artists_with_stats_is_favorite_flag tests/test_library_cache.py::test_get_albums_with_stats_returns_sorted_by_track_count -v
```

Expected: FAIL — functions not defined.

- [ ] **Step 3: Implement both functions**

Add to `backend/library_cache.py` after `toggle_favorite()`:

```python
def get_artists_with_stats(
    days_new: int = 30,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return artists with track count, is_new, is_favorite flags, sorted by track count desc.

    Args:
        days_new: Number of days within which an artist is considered 'new' (first seen).
        conn: Optional connection (used in tests).
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        rows = conn.execute("""
            SELECT
                t.artist,
                COUNT(*) AS track_count,
                MIN(t.first_seen_at) AS first_seen,
                EXISTS(
                    SELECT 1 FROM favorites f
                    WHERE f.type = 'artist' AND LOWER(f.artist) = LOWER(t.artist)
                ) AS is_favorite
            FROM tracks t
            WHERE t.is_live = 0
            GROUP BY t.artist
            ORDER BY track_count DESC
        """).fetchall()
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        from datetime import timedelta
        cutoff_dt = datetime.utcnow() - timedelta(days=days_new)
        result = []
        for row in rows:
            first_seen = row["first_seen"]
            try:
                fs_dt = datetime.fromisoformat(first_seen) if first_seen else None
            except (ValueError, TypeError):
                fs_dt = None
            is_new = fs_dt is not None and fs_dt >= cutoff_dt
            result.append({
                "artist": row["artist"],
                "track_count": row["track_count"],
                "is_new": is_new,
                "is_favorite": bool(row["is_favorite"]),
            })
        return result
    finally:
        if close_after:
            conn.close()


def get_albums_with_stats(
    days_new: int = 30,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return albums with track count, is_new, is_favorite flags, sorted by track count desc.

    Args:
        days_new: Number of days within which an album is considered 'new' (first seen).
        conn: Optional connection (used in tests).
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        rows = conn.execute("""
            SELECT
                t.artist,
                t.album,
                COUNT(*) AS track_count,
                MIN(t.first_seen_at) AS first_seen,
                EXISTS(
                    SELECT 1 FROM favorites f
                    WHERE f.type = 'album'
                      AND LOWER(f.artist) = LOWER(t.artist)
                      AND LOWER(f.album)  = LOWER(t.album)
                ) AS is_favorite
            FROM tracks t
            WHERE t.is_live = 0
            GROUP BY t.artist, t.album
            ORDER BY track_count DESC
        """).fetchall()
        from datetime import timedelta
        cutoff_dt = datetime.utcnow() - timedelta(days=days_new)
        result = []
        for row in rows:
            first_seen = row["first_seen"]
            try:
                fs_dt = datetime.fromisoformat(first_seen) if first_seen else None
            except (ValueError, TypeError):
                fs_dt = None
            is_new = fs_dt is not None and fs_dt >= cutoff_dt
            result.append({
                "artist": row["artist"],
                "album": row["album"],
                "track_count": row["track_count"],
                "is_new": is_new,
                "is_favorite": bool(row["is_favorite"]),
            })
        return result
    finally:
        if close_after:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_library_cache.py::test_get_artists_with_stats_returns_sorted_by_track_count tests/test_library_cache.py::test_get_artists_with_stats_is_favorite_flag tests/test_library_cache.py::test_get_albums_with_stats_returns_sorted_by_track_count -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/test_library_cache.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/library_cache.py tests/test_library_cache.py
git commit -m "feat: add get_artists_with_stats and get_albums_with_stats to library_cache"
```

---

## Task 4: Update `favorites.py` to read from DB

**Files:**
- Modify: `backend/favorites.py`
- Modify: `tests/test_favorites.py` (replace YAML tests with DB tests)

- [ ] **Step 1: Rewrite `tests/test_favorites.py`**

Replace the entire file contents with:

```python
"""Tests for favorites DB loading and is_favorite helper."""
import os
import sqlite3
import tempfile
import pytest

from backend.favorites import is_favorite, Favorites


def make_favorites_db(artists=None, albums=None):
    """Create an in-memory favorites DB and return (conn, db_path)."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE favorites (
            type TEXT NOT NULL, artist TEXT NOT NULL,
            album TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );
    """)
    for a in (artists or []):
        conn.execute("INSERT INTO favorites (type, artist, album) VALUES ('artist', ?, '')", (a,))
    for artist, album in (albums or []):
        conn.execute("INSERT INTO favorites (type, artist, album) VALUES ('album', ?, ?)", (artist, album))
    conn.commit()
    return conn, db_path


def test_is_favorite_artist():
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db(artists=["Miles Davis", "Nick Cave"])
    try:
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
            favs = load_favorites()
        assert is_favorite(favs, "Miles Davis") is True
        assert is_favorite(favs, "miles davis") is True   # case-insensitive
        assert is_favorite(favs, "Bob Dylan") is False
    finally:
        conn.close()
        os.unlink(db_path)


def test_is_favorite_album():
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db(albums=[("Tom Waits", "Rain Dogs")])
    try:
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
            favs = load_favorites()
        assert is_favorite(favs, "Tom Waits", "Rain Dogs") is True
        assert is_favorite(favs, "Tom Waits", "Bone Machine") is False
    finally:
        conn.close()
        os.unlink(db_path)


def test_empty_db_returns_empty_favorites():
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db()
    try:
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
            favs = load_favorites()
        assert is_favorite(favs, "Anyone") is False
    finally:
        conn.close()
        os.unlink(db_path)
```

- [ ] **Step 2: Run tests to verify they fail (old `load_favorites` still takes path)**

```bash
pytest tests/test_favorites.py -v
```

Expected: FAIL — `load_favorites()` called without required `path` argument.

- [ ] **Step 3: Rewrite `backend/favorites.py`**

Replace the entire file:

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Favorites:
    artists: set[str] = field(default_factory=set)   # lowercase artist names
    albums: set[tuple[str, str]] = field(default_factory=set)  # (artist_lower, album_lower)


def load_favorites() -> Favorites:
    """Load favorites from the SQLite library cache. Returns empty Favorites if table missing."""
    from backend import library_cache
    conn = library_cache.ensure_db_initialized()
    try:
        rows = conn.execute("SELECT type, artist, album FROM favorites").fetchall()
        artists = {r["artist"].lower() for r in rows if r["type"] == "artist"}
        albums = {(r["artist"].lower(), r["album"].lower()) for r in rows if r["type"] == "album"}
        return Favorites(artists=artists, albums=albums)
    except Exception:
        return Favorites()
    finally:
        conn.close()


def is_favorite(favs: Favorites, artist: str, album: Optional[str] = None) -> bool:
    """Return True if artist or artist+album is in favorites."""
    if artist.lower() in favs.artists:
        return True
    if album and (artist.lower(), album.lower()) in favs.albums:
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_favorites.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/favorites.py tests/test_favorites.py
git commit -m "feat: load_favorites() reads from SQLite DB instead of YAML"
```

---

## Task 5: Update `generator.py` callers

**Files:**
- Modify: `backend/generator.py`

- [ ] **Step 1: Remove path argument from both `load_favorites()` calls**

In `backend/generator.py`, find and replace both occurrences:

First call (around line 330–336) — replace:
```python
        try:
            from backend.favorites import load_favorites
            from backend.config import get_config as _get_config
            _favs = load_favorites(_get_config().gerbera.favorites_file)
        except Exception:
            _favs = Favorites()
```
with:
```python
        try:
            from backend.favorites import load_favorites
            _favs = load_favorites()
        except Exception:
            _favs = Favorites()
```

Second call (around line 577–582) — replace:
```python
        try:
            from backend.config import get_config as _get_config
            favs = load_favorites(_get_config().gerbera.favorites_file)
        except Exception:
            favs = Favorites()
```
with:
```python
        try:
            favs = load_favorites()
        except Exception:
            favs = Favorites()
```

- [ ] **Step 2: Run generator tests**

```bash
pytest tests/test_generator.py tests/test_generator_prompt.py -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/generator.py
git commit -m "fix: remove path arg from load_favorites() calls in generator"
```

---

## Task 6: Add Pydantic models and API endpoints

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add to `tests/test_api.py`:

```python
def test_get_library_artists_returns_list(client, mocker):
    mocker.patch("backend.library_cache.get_artists_with_stats", return_value=[
        {"artist": "Radiohead", "track_count": 47, "is_new": False, "is_favorite": True},
    ])
    response = client.get("/api/library/artists")
    assert response.status_code == 200
    data = response.json()
    assert "artists" in data
    assert data["artists"][0]["artist"] == "Radiohead"
    assert data["artists"][0]["is_favorite"] is True


def test_get_library_albums_returns_list(client, mocker):
    mocker.patch("backend.library_cache.get_albums_with_stats", return_value=[
        {"artist": "Radiohead", "album": "OK Computer", "track_count": 12, "is_new": True, "is_favorite": False},
    ])
    response = client.get("/api/library/albums")
    assert response.status_code == 200
    data = response.json()
    assert "albums" in data
    assert data["albums"][0]["album"] == "OK Computer"


def test_toggle_favorite_returns_state(client, mocker):
    mocker.patch("backend.library_cache.toggle_favorite", return_value=True)
    response = client.post("/api/favorites/toggle", json={"type": "artist", "artist": "Radiohead", "album": ""})
    assert response.status_code == 200
    assert response.json() == {"is_favorite": True}
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_api.py::test_get_library_artists_returns_list tests/test_api.py::test_get_library_albums_returns_list tests/test_api.py::test_toggle_favorite_returns_state -v
```

Expected: FAIL — endpoints don't exist yet.

- [ ] **Step 3: Add Pydantic models to `backend/models.py`**

Add at the end of `backend/models.py`:

```python
# =============================================================================
# Library / Favorites
# =============================================================================


class ArtistStat(BaseModel):
    artist: str
    track_count: int
    is_new: bool
    is_favorite: bool


class AlbumStat(BaseModel):
    artist: str
    album: str
    track_count: int
    is_new: bool
    is_favorite: bool


class LibraryArtistsResponse(BaseModel):
    artists: list[ArtistStat]


class LibraryAlbumsResponse(BaseModel):
    albums: list[AlbumStat]


class ToggleFavoriteRequest(BaseModel):
    type: Literal["artist", "album"]
    artist: str
    album: str = ""
```

- [ ] **Step 4: Add endpoints to `backend/main.py`**

First, add imports near the top of `main.py` where models are imported:
```python
from backend.models import (
    # ... existing imports ...
    ArtistStat, AlbumStat, LibraryArtistsResponse, LibraryAlbumsResponse, ToggleFavoriteRequest,
)
```

Replace the entire `GET /api/favorites` endpoint (and its section header):

```python
# =============================================================================
# Library / Favorites Endpoints
# =============================================================================


@app.get("/api/library/artists", response_model=LibraryArtistsResponse)
async def get_library_artists(days_new: int = 30) -> LibraryArtistsResponse:
    """Return all artists with track count, is_new and is_favorite flags."""
    rows = await asyncio.to_thread(library_cache.get_artists_with_stats, days_new)
    return LibraryArtistsResponse(artists=[ArtistStat(**r) for r in rows])


@app.get("/api/library/albums", response_model=LibraryAlbumsResponse)
async def get_library_albums(days_new: int = 30) -> LibraryAlbumsResponse:
    """Return all albums with track count, is_new and is_favorite flags."""
    rows = await asyncio.to_thread(library_cache.get_albums_with_stats, days_new)
    return LibraryAlbumsResponse(albums=[AlbumStat(**r) for r in rows])


@app.post("/api/favorites/toggle")
async def toggle_favorite(request: ToggleFavoriteRequest) -> dict:
    """Toggle a favorite artist or album. Returns current state."""
    is_fav = await asyncio.to_thread(
        library_cache.toggle_favorite, request.type, request.artist, request.album
    )
    return {"is_favorite": is_fav}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api.py::test_get_library_artists_returns_list tests/test_api.py::test_get_library_albums_returns_list tests/test_api.py::test_toggle_favorite_returns_state -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all pass (old `test_api.py` tests for `/api/favorites` will need to be removed if they exist — check and delete any that reference that endpoint).

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/main.py tests/test_api.py
git commit -m "feat: add library/artists, library/albums, favorites/toggle endpoints"
```

---

## Task 7: Frontend HTML — Library tab and view

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add Library nav button**

In `frontend/index.html`, find the nav section that contains the Home, Create, Settings buttons. Add the Library button between Create and Settings:

```html
<button class="nav-btn" id="nav-library" data-view="library" aria-label="Library">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>
  </svg>
  <span>Library</span>
</button>
```

- [ ] **Step 2: Add `view-library` section**

Add the following block after the `view-settings` closing `</div>` and before the end of `<main>` (or wherever other views end):

```html
<div id="view-library" class="view hidden">
  <div class="view-header">
    <h1>Library</h1>
    <p class="view-subtitle">Favorisiere Künstler und Alben für deinen Mix</p>
  </div>

  <!-- Tab switcher -->
  <div class="library-tabs" role="tablist">
    <button class="library-tab active" id="lib-tab-artists" role="tab" aria-selected="true" data-tab="artists">
      Künstler
    </button>
    <button class="library-tab" id="lib-tab-albums" role="tab" aria-selected="false" data-tab="albums">
      Alben
    </button>
  </div>

  <!-- Controls -->
  <div class="library-controls">
    <div class="library-search-wrap">
      <svg class="library-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="text" id="lib-search" class="library-search" placeholder="Suchen…" autocomplete="off">
    </div>
    <label class="lib-toggle-label">
      <input type="checkbox" id="lib-filter-new" class="lib-toggle-input">
      <span class="lib-toggle-track"></span>
      <span class="lib-toggle-text">Nur neue</span>
    </label>
    <label class="lib-toggle-label">
      <input type="checkbox" id="lib-filter-favs" class="lib-toggle-input">
      <span class="lib-toggle-track"></span>
      <span class="lib-toggle-text">Nur Favoriten</span>
    </label>
  </div>

  <!-- Loading state -->
  <div id="lib-loading" class="lib-loading hidden">
    <div class="spinner"></div>
    <span>Bibliothek wird geladen…</span>
  </div>

  <!-- Card list -->
  <div id="lib-list" class="lib-list" role="list"></div>

  <!-- Footer -->
  <div class="lib-footer">
    <span id="lib-count"></span>
    <span id="lib-fav-count" class="lib-fav-count"></span>
  </div>
</div>
```

- [ ] **Step 3: Verify HTML is valid (no unclosed tags)**

Open the app in a browser and check the console for parse errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add Library nav tab and view-library HTML structure"
```

---

## Task 8: Frontend CSS — Library styles

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Add styles at end of `frontend/style.css`**

```css
/* ============================================================
   Library View
   ============================================================ */

.library-tabs {
  display: flex;
  gap: 2px;
  background: #111;
  padding: 3px;
  border-radius: 8px;
  width: fit-content;
  margin-bottom: 16px;
}

.library-tab {
  background: transparent;
  border: none;
  color: #888;
  padding: 6px 18px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.library-tab.active {
  background: #e5a00d;
  color: #000;
  font-weight: 600;
}

.library-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.library-search-wrap {
  position: relative;
  flex: 1;
  min-width: 160px;
}

.library-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #555;
  pointer-events: none;
}

.library-search {
  width: 100%;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 7px 10px 7px 32px;
  font-size: 13px;
  color: #ddd;
  box-sizing: border-box;
}

.library-search:focus {
  outline: none;
  border-color: #555;
}

/* Toggle switch */
.lib-toggle-label {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.lib-toggle-input {
  display: none;
}

.lib-toggle-track {
  width: 30px;
  height: 17px;
  background: #333;
  border-radius: 9px;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}

.lib-toggle-track::after {
  content: '';
  position: absolute;
  width: 13px;
  height: 13px;
  background: #666;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.2s, background 0.2s;
}

.lib-toggle-input:checked + .lib-toggle-track {
  background: #2a1f00;
  border: 1px solid #e5a00d;
}

.lib-toggle-input:checked + .lib-toggle-track::after {
  transform: translateX(13px);
  background: #e5a00d;
}

.lib-toggle-text {
  font-size: 12px;
  color: #888;
}

/* Loading */
.lib-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #666;
  font-size: 13px;
  padding: 24px 0;
}

/* Card list */
.lib-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.lib-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 7px;
  padding: 9px 13px;
  transition: border-color 0.15s;
}

.lib-card.is-favorite {
  border-color: #e5a00d;
  background: #1e1e1e;
}

.lib-heart {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  color: #444;
  padding: 0;
  flex-shrink: 0;
  transition: color 0.15s, transform 0.1s;
}

.lib-heart:hover {
  transform: scale(1.15);
}

.lib-card.is-favorite .lib-heart {
  color: #e5a00d;
}

.lib-card-body {
  flex: 1;
  min-width: 0;
}

.lib-card-title {
  color: #ddd;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-card.is-favorite .lib-card-title {
  color: #fff;
}

.lib-card-subtitle {
  color: #555;
  font-size: 11px;
  margin-top: 1px;
}

.lib-badge-new {
  background: #1a3a1a;
  color: #4caf50;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
  letter-spacing: 0.03em;
}

.lib-track-count {
  color: #555;
  font-size: 12px;
  flex-shrink: 0;
  margin-left: auto;
}

/* Footer */
.lib-footer {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #555;
  padding-top: 8px;
  border-top: 1px solid #222;
}

.lib-fav-count {
  color: #e5a00d;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "feat: add Library view CSS styles"
```

---

## Task 9: Frontend JS — Library state, load, render, toggle

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: Add `library` to the `state` object**

Find the `state` object definition (near the top of `app.js`) and add:

```javascript
library: {
  artists: [],   // [{artist, track_count, is_new, is_favorite}]
  albums: [],    // [{artist, album, track_count, is_new, is_favorite}]
  tab: 'artists',
  filterNew: false,
  filterFavs: false,
  search: '',
  loading: false,
},
```

- [ ] **Step 2: Add `loadLibraryView()` and `renderLibrary()`**

Add the following functions before the `DOMContentLoaded` handler:

```javascript
async function loadLibraryView() {
  if (state.library.artists.length > 0 || state.library.albums.length > 0) {
    renderLibrary(); // already loaded
    return;
  }
  state.library.loading = true;
  document.getElementById('lib-loading').classList.remove('hidden');
  document.getElementById('lib-list').innerHTML = '';

  try {
    const [artistsData, albumsData] = await Promise.all([
      apiCall('/library/artists'),
      apiCall('/library/albums'),
    ]);
    state.library.artists = artistsData.artists;
    state.library.albums = albumsData.albums;
  } catch (e) {
    document.getElementById('lib-loading').textContent = 'Fehler beim Laden der Bibliothek.';
    return;
  } finally {
    state.library.loading = false;
    document.getElementById('lib-loading').classList.add('hidden');
  }
  renderLibrary();
}

function renderLibrary() {
  const tab = state.library.tab;
  const items = tab === 'artists' ? state.library.artists : state.library.albums;
  const search = state.library.search.toLowerCase();

  let filtered = items.filter(item => {
    const name = tab === 'artists' ? item.artist : `${item.artist} ${item.album}`;
    if (search && !name.toLowerCase().includes(search)) return false;
    if (state.library.filterNew && !item.is_new) return false;
    if (state.library.filterFavs && !item.is_favorite) return false;
    return true;
  });

  const list = document.getElementById('lib-list');
  list.innerHTML = filtered.map(item => {
    const key = tab === 'artists'
      ? `artist|||${item.artist}`
      : `album|||${item.artist}|||${item.album}`;
    const title = tab === 'artists' ? item.artist : item.album;
    const subtitle = tab === 'albums' ? `<div class="lib-card-subtitle">${escapeHtml(item.artist)}</div>` : '';
    const newBadge = item.is_new ? '<span class="lib-badge-new">NEU</span>' : '';
    const heartChar = item.is_favorite ? '♥' : '♡';
    return `
      <div class="lib-card ${item.is_favorite ? 'is-favorite' : ''}" data-key="${escapeHtml(key)}" role="listitem">
        <button class="lib-heart" data-key="${escapeHtml(key)}" aria-label="Favorit umschalten">${heartChar}</button>
        <div class="lib-card-body">
          <div class="lib-card-title">${escapeHtml(title)}${newBadge}</div>
          ${subtitle}
        </div>
        <span class="lib-track-count">${item.track_count}</span>
      </div>`;
  }).join('');

  const total = filtered.length;
  const favCount = filtered.filter(i => i.is_favorite).length;
  document.getElementById('lib-count').textContent = `${total} ${tab === 'artists' ? 'Künstler' : 'Alben'}`;
  document.getElementById('lib-fav-count').textContent = favCount > 0 ? `♥ ${favCount} Favorit${favCount !== 1 ? 'en' : ''}` : '';
}

async function handleLibraryHeartToggle(key) {
  const [type, artist, album = ''] = key.split('|||');
  const items = type === 'artist' ? state.library.artists : state.library.albums;

  // Optimistic update
  const item = items.find(i =>
    type === 'artist'
      ? i.artist === artist
      : i.artist === artist && i.album === album
  );
  if (!item) return;
  item.is_favorite = !item.is_favorite;
  renderLibrary();

  try {
    const result = await apiCall('/favorites/toggle', {
      method: 'POST',
      body: JSON.stringify({ type, artist, album }),
    });
    item.is_favorite = result.is_favorite;
    renderLibrary();
  } catch (e) {
    // Revert on error
    item.is_favorite = !item.is_favorite;
    renderLibrary();
  }
}
```

- [ ] **Step 3: Wire up nav, tab, search, filter events**

In the `DOMContentLoaded` handler, add:

```javascript
// Library nav
document.getElementById('nav-library').addEventListener('click', () => {
  showView('library');
  loadLibraryView();
});

// Library tab switching
document.getElementById('lib-tab-artists').addEventListener('click', () => {
  state.library.tab = 'artists';
  document.getElementById('lib-tab-artists').classList.add('active');
  document.getElementById('lib-tab-artists').setAttribute('aria-selected', 'true');
  document.getElementById('lib-tab-albums').classList.remove('active');
  document.getElementById('lib-tab-albums').setAttribute('aria-selected', 'false');
  renderLibrary();
});

document.getElementById('lib-tab-albums').addEventListener('click', () => {
  state.library.tab = 'albums';
  document.getElementById('lib-tab-albums').classList.add('active');
  document.getElementById('lib-tab-albums').setAttribute('aria-selected', 'true');
  document.getElementById('lib-tab-artists').classList.remove('active');
  document.getElementById('lib-tab-artists').setAttribute('aria-selected', 'false');
  renderLibrary();
});

// Search
document.getElementById('lib-search').addEventListener('input', e => {
  state.library.search = e.target.value;
  renderLibrary();
});

// Filter toggles
document.getElementById('lib-filter-new').addEventListener('change', e => {
  state.library.filterNew = e.target.checked;
  renderLibrary();
});

document.getElementById('lib-filter-favs').addEventListener('change', e => {
  state.library.filterFavs = e.target.checked;
  renderLibrary();
});

// Heart toggle (event delegation)
document.getElementById('lib-list').addEventListener('click', e => {
  const btn = e.target.closest('.lib-heart');
  if (!btn) return;
  handleLibraryHeartToggle(btn.dataset.key);
});
```

- [ ] **Step 4: Ensure `showView('library')` works**

Find the `showView()` function in `app.js`. It typically hides all `.view` divs and shows the one matching the name. Verify that `view-library` will be shown when `showView('library')` is called. If `showView` uses a pattern like `document.getElementById('view-' + name)`, it will work automatically.

- [ ] **Step 5: Start the dev server and manually test**

```bash
uvicorn backend.main:app --reload --port 5765
```

1. Open `http://localhost:5765` and hard-refresh (Cmd+Shift+R)
2. Click the "Library" nav button — should navigate to the library view and show a loading spinner briefly
3. Artist cards appear, sorted by track count, with track count on the right
4. Click a heart → card gets amber border, heart fills amber
5. Click again → reverts to grey
6. Toggle "Nur Favoriten" → only hearted artists show
7. Switch to "Alben" tab → album cards appear
8. Type in search box → list filters in real time
9. Refresh page → favorites persist (stored in DB)

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/app.js
git commit -m "feat: Library browser view with artist/album heart toggle and filters"
```

---

## Self-Review

**Spec coverage:**
- ✅ favorites table in SQLite — Task 1
- ✅ `toggle_favorite` — Task 2
- ✅ `get_artists_with_stats` / `get_albums_with_stats` — Task 3
- ✅ `load_favorites()` reads DB — Task 4
- ✅ `generator.py` callers updated — Task 5
- ✅ API endpoints — Task 6
- ✅ Library nav tab — Task 7
- ✅ CSS styles — Task 8
- ✅ JS state, load, render, toggle — Task 9
- ✅ `GET /api/favorites` removed — Task 6
- ✅ NEU badge (is_new) — Task 9 (renderLibrary)
- ✅ "Nur neue" + "Nur Favoriten" toggles — Task 9
- ✅ Sorted by track count — Task 3 (ORDER BY track_count DESC)
- ✅ Optimistic UI update — Task 9 (handleLibraryHeartToggle)

**Type consistency:** `ArtistStat` / `AlbumStat` used consistently in Task 6 models and endpoint returns. `data-key` format `type|||artist|||album` used consistently in `renderLibrary` and `handleLibraryHeartToggle`.

**No placeholders found.**
