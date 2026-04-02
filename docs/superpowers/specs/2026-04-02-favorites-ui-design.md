# Favorites UI — Design Spec

**Date:** 2026-04-02
**Status:** Approved

## Overview

Replace the YAML-based favorites system with a UI-driven Library browser. Users mark favorite artists and albums directly in the app; data is persisted in SQLite. The existing `generate_favorites_playlist_stream` and LLM prompt tagging continue to work without changes.

## Goals

- No more manual editing of `favorites.yaml`
- Browse the full library, sorted by track count
- Mark/unmark artists and albums as favorites with a single click
- Spot recently added content via "NEU" badge and filter toggle

## Non-Goals

- Track-level favorites (artist and album granularity only)
- Playlist editing or playback from this view
- Changing the 70/30 split logic in `generate_favorites_playlist_stream`

---

## Data Model

New table in `library_cache.db`:

```sql
CREATE TABLE IF NOT EXISTS favorites (
    type      TEXT NOT NULL,          -- 'artist' or 'album'
    artist    TEXT NOT NULL,
    album     TEXT NOT NULL DEFAULT '',  -- empty string for artist-level favorites
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(type, artist, album)
);
```

Migration: added via `CREATE TABLE IF NOT EXISTS` in `init_db()` / `init_schema()`, alongside the existing `tracks` table. No `ALTER TABLE` needed (new table, not new column).

---

## Backend

### `library_cache.py` — new functions

**`get_artists_with_stats(days_new: int = 30) -> list[dict]`**

```sql
SELECT
    artist,
    COUNT(*) AS track_count,
    MIN(first_seen_at) AS first_seen,
    EXISTS(SELECT 1 FROM favorites WHERE type='artist' AND favorites.artist=t.artist) AS is_favorite
FROM tracks t
WHERE is_live = 0
GROUP BY artist
ORDER BY track_count DESC
```

Returns: `[{artist, track_count, is_new: bool, is_favorite: bool}]`
`is_new = first_seen > now - days_new days`

**`get_albums_with_stats(days_new: int = 30) -> list[dict]`**

Same pattern, grouped by `(artist, album)`.

**`toggle_favorite(fav_type: str, artist: str, album: str = "") -> bool`**

Insert-or-delete. Returns `True` if now a favorite, `False` if removed.

### `favorites.py` — updated `load_favorites()`

`load_favorites()` reads from the DB instead of a YAML file. Signature change: no `path` argument. `is_favorite()` unchanged.

```python
def load_favorites() -> Favorites:
    conn = ensure_db_initialized()
    try:
        rows = conn.execute("SELECT type, artist, album FROM favorites").fetchall()
        artists = {r["artist"].lower() for r in rows if r["type"] == "artist"}
        albums = {(r["artist"].lower(), r["album"].lower()) for r in rows if r["type"] == "album"}
        return Favorites(artists=artists, albums=albums)
    finally:
        conn.close()
```

All callers (`generator.py`) updated to call `load_favorites()` without a path argument.

### `main.py` — new endpoints

**`GET /api/library/artists?days_new=30`**

Response:
```json
{
  "artists": [
    {"artist": "Radiohead", "track_count": 89, "is_new": true, "is_favorite": true},
    ...
  ]
}
```

**`GET /api/library/albums?days_new=30`**

Response:
```json
{
  "albums": [
    {"artist": "Radiohead", "album": "OK Computer", "track_count": 12, "is_new": false, "is_favorite": false},
    ...
  ]
}
```

**`POST /api/favorites/toggle`**

Body: `{"type": "artist"|"album", "artist": "...", "album": "..."}`
Response: `{"is_favorite": true|false}`

The existing `GET /api/favorites` endpoint is removed (was YAML-based and unused by the frontend).

---

## Frontend

### Navigation

New "Library" tab added to the main nav bar, between "Create" and "Settings". Icon: filled heart SVG. Active state: amber border + tinted background (matches existing nav style).

### View: `view-library`

**State added to `state` object:**
```javascript
library: {
  artists: [],      // [{artist, track_count, is_new, is_favorite}]
  albums: [],       // [{artist, album, track_count, is_new, is_favorite}]
  tab: 'artists',   // 'artists' | 'albums'
  filterNew: false,
  filterFavs: false,
  search: '',
  loading: false,
}
```

**Layout:**
1. Tab switcher: `Künstler` | `Alben` (pill style, amber active)
2. Controls row: search input + "Nur neue" toggle + "Nur Favoriten" toggle
3. Scrollable list of cards
4. Footer: total count + favorited count

**Card:**
- Heart button (♥ amber if favorite, ♡ grey if not) — left edge
- Artist name (or Album + Artist subtitle)
- Track count — right-aligned, muted
- "NEU" badge (green) if `is_new`
- Favorited cards: amber border `1px solid #e5a00d`

**Interactions:**
- Heart click: calls `POST /api/favorites/toggle`, updates card state optimistically (no reload)
- Search: client-side filter on already-loaded data (no extra API call)
- Toggle "Nur neue": client-side filter
- Toggle "Nur Favoriten": client-side filter
- Tab switch: loads the other list if not yet fetched

### Loading behavior

`loadLibraryView()` is called when the Library tab is first shown. Fetches artists and albums in parallel. Shows a spinner during load.

---

## Migration / Compatibility

- `config.gerbera.favorites_file` field remains in config schema but is no longer read at runtime. It can be removed in a future cleanup.
- On first run after deploy: favorites table is empty. Users build their favorites list in the UI.
- No data migration from YAML needed — the YAML list was manual anyway.

---

## Testing

- Unit test `toggle_favorite`: insert → returns True; call again → returns False (removed)
- Unit test `load_favorites()`: no-path signature, reads from DB
- Unit test `get_artists_with_stats()`: returns correct track counts and is_new flag
- Integration: `POST /api/favorites/toggle` + `GET /api/library/artists` reflect the change
