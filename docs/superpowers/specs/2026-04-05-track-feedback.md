# Track Feedback Spec

**Feature:** Thumbs up / thumbs down per track in generated playlists, influencing future playlist generation via prompt context.

---

## Overview

Users can rate individual tracks in any playlist (current result or history) with a thumbs up or thumbs down. Ratings are stored persistently and injected as context into all future LLM generation prompts.

---

## Data Model

New table `track_feedback` in the existing `library_cache.db` (created alongside the other tables in `get_db_connection()`):

```sql
CREATE TABLE IF NOT EXISTS track_feedback (
    gerbera_id  INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    artist      TEXT NOT NULL,
    album       TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating IN (1, -1)),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

- One row per track. `gerbera_id` is the primary key — upsert on conflict.
- `rating`: `1` = thumbs up, `-1` = thumbs down.
- Deleting a rating: row is deleted (no `rating=0` rows stored).

---

## Backend

### `library_cache.py`

Two new functions:

**`save_track_feedback(gerbera_id, title, artist, album, rating)`**
- `rating=1` or `rating=-1`: upsert (`INSERT OR REPLACE`)
- `rating=0`: delete the row (toggle off)

**`get_track_feedback() → dict[int, int]`**
- Returns `{gerbera_id: rating}` for all rated tracks.
- Used by the generator and by the frontend on load.

Table is initialized in `get_db_connection()` alongside existing tables.

### `main.py`

New endpoint:

```
POST /api/feedback/track
Request:  { gerbera_id: int, title: str, artist: str, album: str, rating: int }
Response: { ok: true }
```

`rating` must be `1`, `-1`, or `0`. Returns 400 for invalid values.

New read endpoint:

```
GET /api/feedback/tracks
Response: { feedback: { "<gerbera_id>": 1 | -1, ... } }
```

### `generator.py`

In `generate_playlist_stream()` and `generate_favorites_playlist_stream()`, before building the generation prompt:

1. Call `get_track_feedback()`
2. Split into liked (rating=1) and disliked (rating=-1)
3. Cap at 20 each (most recent first)
4. If any feedback exists, append to `generation_parts`:

```
User feedback from previous playlists:
- Liked: "Karma Police" by Radiohead, "Black" by Pearl Jam
- Disliked: "Wonderwall" by Oasis
Prefer artists and styles similar to the liked tracks. Avoid artists and styles similar to the disliked tracks.
```

If no feedback exists, nothing is added to the prompt.

---

## Frontend

### `app.js`

**Loading feedback state:**
- On playlist render (both results view and history view), fetch `GET /api/feedback/tracks` once and store in `state.trackFeedback` (`{gerbera_id: rating}`).

**Track HTML** — add two buttons between track info and remove button:

```html
<button class="track-thumb track-thumb-up [active]"
        data-gerbera-id="..." data-rating="1"
        aria-label="Thumbs up">👍</button>
<button class="track-thumb track-thumb-down [active]"
        data-gerbera-id="..." data-rating="-1"
        aria-label="Thumbs down">👎</button>
```

CSS class `active` applied when the track's current rating matches the button's rating.

**Click handler** (event delegation on the track container):
1. Read `gerbera_id` and `rating` from button dataset
2. Determine new rating: if current rating equals clicked rating → `0` (toggle off), else → clicked rating
3. Optimistic UI update: update button active states immediately
4. `POST /api/feedback/track` with new rating
5. Update `state.trackFeedback`
6. On error: revert UI

**History view:** Same buttons, same logic. The remove button (`×`) is already absent in history view, so no layout conflict.

### `style.css`

```css
.track-thumb {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    opacity: 0.3;
    padding: 2px 4px;
    transition: opacity 0.15s, transform 0.1s;
}
.track-thumb:hover { opacity: 0.7; }
.track-thumb.active { opacity: 1; }
.track-thumb-up.active  { color: var(--success); }
.track-thumb-down.active { color: var(--error); }
```

---

## Behaviour Summary

| Action | Result |
|--------|--------|
| Click 👍 (neutral) | Rate +1, button active |
| Click 👎 (neutral) | Rate -1, button active |
| Click active 👍 again | Remove rating, both neutral |
| Click 👎 when 👍 active | Switch to -1, 👍 goes neutral |
| Click in history view | Same as above |

---

## Out of Scope

- Feedback statistics / dashboard
- Artist-level aggregation
- Feedback export
- Undo beyond toggle
