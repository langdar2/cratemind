# Track Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add thumbs up/down per-track feedback to generated playlists and inject that feedback as prompt context into all future playlist generation calls.

**Architecture:** New `track_feedback` table in `library_cache.db`. Two new backend functions (`save_track_feedback`, `get_track_feedback`) in `library_cache.py`. Two new API endpoints in `main.py`. Feedback injected in `generator.py` before the LLM call. Frontend adds 👍/👎 buttons to each track row in both the results view and the history view.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (stdlib), Vanilla JS ES6+

---

## File Map

| File | Change |
|---|---|
| `backend/library_cache.py` | Add `track_feedback` table to `init_schema()` + two new functions |
| `backend/main.py` | Add `POST /api/feedback/track` and `GET /api/feedback/tracks` endpoints |
| `backend/generator.py` | Inject feedback context into generation prompt |
| `frontend/app.js` | Add `state.trackFeedback`, thumb buttons in track HTML, click handler |
| `frontend/style.css` | Style `.track-thumb` buttons |

---

### Task 1: DB schema + library_cache functions

**Files:**
- Modify: `backend/library_cache.py` (`init_schema` function + two new functions at end of file)
- Modify: `tests/test_library_cache.py` (or create if absent: `tests/test_track_feedback.py`)

- [ ] **Step 1: Add `track_feedback` table to `init_schema`**

In `backend/library_cache.py`, inside `init_schema()`, the `conn.executescript("""...""")` block ends with the favorites index (around line 292). Add the new table to the executescript block, before the closing `"""`):

```sql
        -- Track feedback: user thumbs up/down per track
        CREATE TABLE IF NOT EXISTS track_feedback (
            gerbera_id  INTEGER PRIMARY KEY,
            title       TEXT NOT NULL,
            artist      TEXT NOT NULL,
            album       TEXT NOT NULL,
            rating      INTEGER NOT NULL CHECK (rating IN (1, -1)),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
```

- [ ] **Step 2: Add `save_track_feedback` function**

Add at the end of `backend/library_cache.py`:

```python
def save_track_feedback(
    gerbera_id: int,
    title: str,
    artist: str,
    album: str,
    rating: int,
) -> None:
    """Save or delete a track rating.

    rating=1 or -1: upsert the row.
    rating=0: delete the row (toggle off).
    """
    with get_db_connection() as conn:
        if rating == 0:
            conn.execute(
                "DELETE FROM track_feedback WHERE gerbera_id = ?",
                (gerbera_id,),
            )
        else:
            conn.execute(
                """INSERT INTO track_feedback (gerbera_id, title, artist, album, rating)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(gerbera_id) DO UPDATE SET
                       rating = excluded.rating,
                       title  = excluded.title,
                       artist = excluded.artist,
                       album  = excluded.album,
                       created_at = CURRENT_TIMESTAMP""",
                (gerbera_id, title, artist, album, rating),
            )
        conn.commit()
```

- [ ] **Step 3: Add `get_track_feedback` function**

Add immediately after `save_track_feedback`:

```python
def get_track_feedback() -> dict[int, int]:
    """Return all track ratings as {gerbera_id: rating}.

    rating is 1 (liked) or -1 (disliked).
    Returns empty dict if no feedback exists.
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT gerbera_id, rating FROM track_feedback ORDER BY created_at DESC"
        ).fetchall()
    return {row["gerbera_id"]: row["rating"] for row in rows}
```

- [ ] **Step 4: Verify `get_db_connection` supports context manager**

Check that `get_db_connection()` can be used as a context manager (`with get_db_connection() as conn:`). In `backend/library_cache.py`, find `get_db_connection()`. SQLite connections support context manager protocol natively — confirm there is no custom `__enter__`/`__exit__` that would break this. If `get_db_connection` returns a plain `sqlite3.Connection`, `with conn:` only commits/rolls back — it does NOT close the connection. This is fine.

If the existing code uses `conn = get_db_connection()` without `with`, just follow the same pattern:

```python
def save_track_feedback(...) -> None:
    conn = get_db_connection()
    try:
        if rating == 0:
            conn.execute("DELETE FROM track_feedback WHERE gerbera_id = ?", (gerbera_id,))
        else:
            conn.execute("""INSERT INTO track_feedback ...""", (...))
        conn.commit()
    finally:
        conn.close()

def get_track_feedback() -> dict[int, int]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT gerbera_id, rating FROM track_feedback ORDER BY created_at DESC"
        ).fetchall()
        return {row["gerbera_id"]: row["rating"] for row in rows}
    finally:
        conn.close()
```

Use whichever pattern matches the rest of the file.

- [ ] **Step 5: Write tests**

Create `tests/test_track_feedback.py`:

```python
import pytest
from backend import library_cache


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point library_cache at a fresh temp database for each test."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(library_cache, "DB_PATH", db)
    conn = library_cache.get_db_connection()
    library_cache.init_schema(conn)
    conn.close()
    yield


def test_save_and_get_feedback():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    fb = library_cache.get_track_feedback()
    assert fb == {1: 1}


def test_dislike_overwrites_like():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", -1)
    fb = library_cache.get_track_feedback()
    assert fb == {1: -1}


def test_toggle_off_removes_rating():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 0)
    fb = library_cache.get_track_feedback()
    assert fb == {}


def test_multiple_tracks():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(2, "Song B", "Artist B", "Album B", -1)
    fb = library_cache.get_track_feedback()
    assert fb[1] == 1
    assert fb[2] == -1


def test_get_feedback_empty():
    assert library_cache.get_track_feedback() == {}
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_track_feedback.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/library_cache.py tests/test_track_feedback.py
git commit -m "feat: add track_feedback table and save/get functions to library_cache"
```

---

### Task 2: API endpoints

**Files:**
- Modify: `backend/main.py` (add two endpoints + Pydantic models)
- Modify: `backend/models.py` (add request/response models)

- [ ] **Step 1: Add Pydantic models to `backend/models.py`**

Find the end of the models file and add:

```python
class TrackFeedbackRequest(BaseModel):
    """Request to save or remove a track rating."""
    gerbera_id: int
    title: str
    artist: str
    album: str
    rating: int  # 1, -1, or 0 (remove)


class TrackFeedbackResponse(BaseModel):
    ok: bool


class TrackFeedbackListResponse(BaseModel):
    feedback: dict[int, int]
```

- [ ] **Step 2: Add endpoints to `backend/main.py`**

In `main.py`, add the import at the top alongside other library_cache imports:

```python
from backend.models import (
    ...
    TrackFeedbackRequest,
    TrackFeedbackResponse,
    TrackFeedbackListResponse,
)
```

Then add two endpoints. A good place is near the `/api/favorites/toggle` endpoint (search for it). Add after it:

```python
@app.post("/api/feedback/track", response_model=TrackFeedbackResponse)
async def save_track_feedback(request: TrackFeedbackRequest) -> TrackFeedbackResponse:
    """Save or remove a thumbs up/down rating for a track."""
    if request.rating not in (1, -1, 0):
        raise HTTPException(status_code=400, detail="rating must be 1, -1, or 0")
    await asyncio.to_thread(
        library_cache.save_track_feedback,
        request.gerbera_id,
        request.title,
        request.artist,
        request.album,
        request.rating,
    )
    return TrackFeedbackResponse(ok=True)


@app.get("/api/feedback/tracks", response_model=TrackFeedbackListResponse)
async def get_track_feedback() -> TrackFeedbackListResponse:
    """Return all track ratings."""
    feedback = await asyncio.to_thread(library_cache.get_track_feedback)
    return TrackFeedbackListResponse(feedback=feedback)
```

- [ ] **Step 3: Verify the server starts**

```bash
uvicorn backend.main:app --reload --port 5765
```

Expected: no import errors, server starts.

- [ ] **Step 4: Smoke-test endpoints**

```bash
curl -s -X POST http://localhost:5765/api/feedback/track \
  -H "Content-Type: application/json" \
  -d '{"gerbera_id": 99, "title": "Test", "artist": "Artist", "album": "Album", "rating": 1}'
# Expected: {"ok":true}

curl -s http://localhost:5765/api/feedback/tracks
# Expected: {"feedback":{"99":1}}

curl -s -X POST http://localhost:5765/api/feedback/track \
  -H "Content-Type: application/json" \
  -d '{"gerbera_id": 99, "title": "Test", "artist": "Artist", "album": "Album", "rating": 0}'
# Expected: {"ok":true}

curl -s http://localhost:5765/api/feedback/tracks
# Expected: {"feedback":{}}
```

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/main.py
git commit -m "feat: add POST /api/feedback/track and GET /api/feedback/tracks endpoints"
```

---

### Task 3: Inject feedback into generation prompt

**Files:**
- Modify: `backend/generator.py` (two functions: `generate_playlist_stream` and `generate_favorites_playlist_stream`)

- [ ] **Step 1: Update `get_track_feedback` to return full rows**

The current `get_track_feedback()` in `backend/library_cache.py` returns `dict[int, int]`. For useful prompt context we need title and artist. Change it to return full rows.

Update `backend/library_cache.py`:

```python
def get_track_feedback() -> list[dict]:
    """Return all track ratings as list of dicts with gerbera_id, title, artist, album, rating.

    Ordered by created_at DESC (most recent first).
    Returns empty list if no feedback exists.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT gerbera_id, title, artist, album, rating "
            "FROM track_feedback ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

Update `backend/models.py` `TrackFeedbackListResponse` to match:

```python
class TrackFeedbackListResponse(BaseModel):
    feedback: dict[int, int]  # keep as-is for the API endpoint (frontend only needs gerbera_id → rating)
```

Update `backend/main.py` `get_track_feedback` endpoint to convert list → dict for the API response:

```python
@app.get("/api/feedback/tracks", response_model=TrackFeedbackListResponse)
async def get_track_feedback_endpoint() -> TrackFeedbackListResponse:
    """Return all track ratings as {gerbera_id: rating}."""
    rows = await asyncio.to_thread(library_cache.get_track_feedback)
    return TrackFeedbackListResponse(feedback={r["gerbera_id"]: r["rating"] for r in rows})
```

Also update the test in `tests/test_track_feedback.py` — `get_track_feedback()` now returns a list:

```python
def test_save_and_get_feedback():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    fb = library_cache.get_track_feedback()
    assert len(fb) == 1
    assert fb[0]["gerbera_id"] == 1
    assert fb[0]["rating"] == 1

def test_dislike_overwrites_like():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", -1)
    fb = library_cache.get_track_feedback()
    assert fb[0]["rating"] == -1

def test_toggle_off_removes_rating():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 0)
    assert library_cache.get_track_feedback() == []

def test_multiple_tracks():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(2, "Song B", "Artist B", "Album B", -1)
    fb = library_cache.get_track_feedback()
    ratings = {r["gerbera_id"]: r["rating"] for r in fb}
    assert ratings[1] == 1
    assert ratings[2] == -1

def test_get_feedback_empty():
    assert library_cache.get_track_feedback() == []
```

- [ ] **Step 2: Add `_build_feedback_prompt` helper in `generator.py`**

Add to `backend/generator.py` after the imports:

```python
def _build_feedback_prompt(rows: list[dict], limit: int = 20) -> str | None:
    """Build a feedback context block for the generation prompt.

    rows: list of dicts with keys gerbera_id, title, artist, album, rating.
          Expected in created_at DESC order (most recent first).
    Returns None if rows is empty.
    """
    if not rows:
        return None

    liked = [r for r in rows if r["rating"] == 1][:limit]
    disliked = [r for r in rows if r["rating"] == -1][:limit]

    if not liked and not disliked:
        return None

    parts = ["User feedback from previous playlists:"]
    if liked:
        track_list = ", ".join(f'"{r["title"]}" by {r["artist"]}' for r in liked)
        parts.append(f"- Liked: {track_list}")
    if disliked:
        track_list = ", ".join(f'"{r["title"]}" by {r["artist"]}' for r in disliked)
        parts.append(f"- Disliked: {track_list}")
    parts.append(
        "Prefer artists and styles similar to the liked tracks. "
        "Avoid artists and styles similar to the disliked tracks."
    )
    return "\n".join(parts)
```

- [ ] **Step 3: Inject feedback into `generate_playlist_stream`**

In `backend/generator.py`, find `generate_playlist_stream`. Just before `generation_parts = []` (around line 342), add:

```python
        # Load track feedback for prompt context
        try:
            _feedback_rows = library_cache.get_track_feedback()
            _feedback_block = _build_feedback_prompt(_feedback_rows)
        except Exception:
            _feedback_block = None
```

Then after `if additional_notes:` block and before the final `generation_parts.append(f"\nSelect {track_count} tracks...")` line, add:

```python
        if _feedback_block:
            generation_parts.append(_feedback_block)
```

- [ ] **Step 4: Inject feedback into `generate_favorites_playlist_stream`**

Find `generate_favorites_playlist_stream` in `backend/generator.py`. Locate where it builds its generation prompt (search for `generation_parts` or `generation_prompt` inside that function). Apply the same two additions as Step 3.

If `generate_favorites_playlist_stream` does not use `generation_parts`, find where the prompt string is constructed and append `_feedback_block` before the track list section using string concatenation.

- [ ] **Step 5: Run existing tests**

```bash
pytest tests/test_track_feedback.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/library_cache.py backend/main.py backend/generator.py tests/test_track_feedback.py
git commit -m "feat: inject track feedback context into playlist generation prompt"
```

---

### Task 4: Frontend — buttons, state, click handler, CSS

**Files:**
- Modify: `frontend/app.js` (state, track HTML, click handler, feedback load)
- Modify: `frontend/style.css` (button styles)

- [ ] **Step 1: Add `trackFeedback` to `state`**

In `frontend/app.js`, find the `const state = {` block (line 69). Add inside it, after the `rec:` block:

```js
    // Track feedback: {gerbera_id: rating} where rating is 1 or -1
    trackFeedback: {},
```

- [ ] **Step 2: Add `loadTrackFeedback` function**

Add this function in `frontend/app.js` (near other API helper functions):

```js
async function loadTrackFeedback() {
    try {
        const data = await apiCall('/feedback/tracks');
        state.trackFeedback = {};
        for (const [id, rating] of Object.entries(data.feedback || {})) {
            state.trackFeedback[parseInt(id, 10)] = rating;
        }
    } catch (e) {
        console.warn('Failed to load track feedback:', e);
    }
}
```

- [ ] **Step 3: Add thumb buttons to playlist track HTML**

In `frontend/app.js`, find `updatePlaylist` (the function that renders `container.innerHTML`). The current track HTML ends with:

```js
            <button class="track-remove" tabindex="0" data-rating-key="${escapeHtml(track.rating_key)}"
                    aria-label="Remove ${escapeHtml(track.title)}">&times;</button>
        </div>
```

Replace with:

```js
            <div class="track-actions">
                <button class="track-thumb track-thumb-up${state.trackFeedback[track.rating_key] === 1 ? ' active' : ''}"
                        data-gerbera-id="${escapeHtml(String(track.rating_key))}"
                        data-rating="1"
                        aria-label="Thumbs up for ${escapeHtml(track.title)}">👍</button>
                <button class="track-thumb track-thumb-down${state.trackFeedback[track.rating_key] === -1 ? ' active' : ''}"
                        data-gerbera-id="${escapeHtml(String(track.rating_key))}"
                        data-rating="-1"
                        aria-label="Thumbs down for ${escapeHtml(track.title)}">👎</button>
                <button class="track-remove" tabindex="0" data-rating-key="${escapeHtml(track.rating_key)}"
                        aria-label="Remove ${escapeHtml(track.title)}">&times;</button>
            </div>
        </div>
```

- [ ] **Step 4: Call `loadTrackFeedback` before rendering playlists**

In `frontend/app.js`, find the function `updatePlaylist` (or wherever `updatePlaylist()` is called after generation completes and when a saved result is loaded). Make `loadTrackFeedback` run before the render.

Find the block in `loadSavedResult` that calls `updatePlaylist()` (around line 656):

```js
            updateView();
            updateMode();
            updateStep();
            updatePlaylist();
```

Change to:

```js
            updateView();
            updateMode();
            updateStep();
            await loadTrackFeedback();
            updatePlaylist();
```

Also find where playlist generation completes and calls `updatePlaylist()` — add `await loadTrackFeedback()` before it. Search for the SSE done handler that sets `state.playlist` and calls `updatePlaylist()`.

- [ ] **Step 5: Add click handler for thumb buttons**

In `frontend/app.js`, find the click handler on `playlist-tracks` (around line 2697):

```js
    document.getElementById('playlist-tracks').addEventListener('click', e => {
        const removeBtn = e.target.closest('.track-remove');
        if (!removeBtn) return;
        ...
    });
```

Replace with:

```js
    document.getElementById('playlist-tracks').addEventListener('click', async e => {
        // Remove button
        const removeBtn = e.target.closest('.track-remove');
        if (removeBtn) {
            const ratingKey = removeBtn.dataset.ratingKey;
            const removedIndex = state.playlist.findIndex(t => t.rating_key === ratingKey);
            state.playlist = state.playlist.filter(t => t.rating_key !== ratingKey);
            if (state.selectedTrackKey === ratingKey) {
                if (state.playlist.length > 0) {
                    const nextIndex = Math.min(removedIndex, state.playlist.length - 1);
                    state.selectedTrackKey = state.playlist[nextIndex].rating_key;
                } else {
                    state.selectedTrackKey = null;
                }
            }
            updatePlaylist();
            return;
        }

        // Thumb buttons
        const thumbBtn = e.target.closest('.track-thumb');
        if (!thumbBtn) return;

        const gerberaId = parseInt(thumbBtn.dataset.gerberaId, 10);
        const clickedRating = parseInt(thumbBtn.dataset.rating, 10);
        const currentRating = state.trackFeedback[gerberaId] || 0;
        const newRating = currentRating === clickedRating ? 0 : clickedRating;

        // Find track metadata
        const track = state.playlist.find(t => parseInt(t.rating_key, 10) === gerberaId);
        if (!track) return;

        // Optimistic UI update
        const prevRating = state.trackFeedback[gerberaId] || 0;
        if (newRating === 0) {
            delete state.trackFeedback[gerberaId];
        } else {
            state.trackFeedback[gerberaId] = newRating;
        }
        updatePlaylist();

        try {
            await apiCall('/feedback/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    gerbera_id: gerberaId,
                    title: track.title,
                    artist: track.artist,
                    album: track.album,
                    rating: newRating,
                }),
            });
        } catch (e) {
            // Revert on error
            if (prevRating === 0) {
                delete state.trackFeedback[gerberaId];
            } else {
                state.trackFeedback[gerberaId] = prevRating;
            }
            updatePlaylist();
            console.error('Failed to save feedback:', e);
        }
    });
```

- [ ] **Step 6: Add CSS**

In `frontend/style.css`, add after the `.track-remove` styles (search for `.track-remove` to find the right location):

```css
.track-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
}

.track-thumb {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    opacity: 0.25;
    padding: 2px 4px;
    border-radius: var(--radius-sm);
    transition: opacity 0.15s, transform 0.1s;
    line-height: 1;
}

.track-thumb:hover {
    opacity: 0.65;
    transform: scale(1.15);
}

.track-thumb.active {
    opacity: 1;
}

.track-thumb-up.active {
    color: var(--success);
}

.track-thumb-down.active {
    color: var(--error);
}
```

- [ ] **Step 7: Verify in browser**

Start the server:
```bash
uvicorn backend.main:app --reload --port 5765
```

Open http://localhost:5765, load or generate a playlist. Verify:
- 👍 and 👎 appear on each track
- Clicking 👍 highlights it green, clicking again un-highlights
- Clicking 👎 highlights it red
- Clicking 👎 when 👍 is active: 👍 clears, 👎 activates
- Reload the page and open the same playlist — ratings are still shown

- [ ] **Step 8: Commit**

```bash
git add frontend/app.js frontend/style.css
git commit -m "feat: add thumbs up/down feedback buttons to playlist tracks"
git push
```
