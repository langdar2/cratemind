"""Playlist generation with library validation."""

import json
import json as _json
import logging
import random as _random
import re as _re
import unicodedata as _unicodedata
from collections.abc import Generator
from datetime import datetime
from datetime import date as _date
from pathlib import Path

from backend.llm_client import get_llm_client
from backend.models import GenerateResponse, Track
from backend import library_cache
from backend.favorites import Favorites, is_favorite, load_favorites
from backend.als_recommender import recommender as _als_recommender

logger = logging.getLogger(__name__)


def _build_feedback_prompt(rows: list[dict], limit: int = 20) -> str | None:
    """Build a structured feedback context block for the LLM generation prompt.

    Extracts unique artists from liked and disliked tracks so the LLM gets
    explicit, actionable instructions rather than guessing from track titles.

    rows: list of dicts with keys title, artist, album, rating.
          Expected in created_at DESC order (most recent first).
    limit: max tracks per sentiment to include.
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
        liked_artists = list(dict.fromkeys(r["artist"] for r in liked))
        liked_tracks = ", ".join(f'"{r["title"]}"' for r in liked[:5])
        parts.append(
            f"- Liked tracks: {liked_tracks}"
            + (f" (and {len(liked) - 5} more)" if len(liked) > 5 else "")
        )
        parts.append(f"- Preferred artists: {', '.join(liked_artists)}")

    if disliked:
        disliked_artists = list(dict.fromkeys(r["artist"] for r in disliked))
        disliked_tracks = ", ".join(f'"{r["title"]}"' for r in disliked[:5])
        parts.append(
            f"- Disliked tracks: {disliked_tracks}"
            + (f" (and {len(disliked) - 5} more)" if len(disliked) > 5 else "")
        )
        parts.append(f"- Avoid these artists: {', '.join(disliked_artists)}")

    parts.append(
        "Strongly prefer tracks by the preferred artists and in similar styles. "
        "Do not select tracks by artists listed under 'Avoid'."
    )
    return "\n".join(parts)


# Fuzzy matching threshold (0-100 scale, used with token_sort_ratio)
FUZZ_THRESHOLD = 72


def simplify_string(s: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, strip accents, remove punctuation."""
    s = _unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if _unicodedata.category(c) != "Mn")
    return _re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def normalize_artist(artist: str) -> list[str]:
    """Return artist name variants for fuzzy matching (handles 'and' vs '&')."""
    variants = [artist]
    if " & " in artist:
        variants.append(artist.replace(" & ", " and "))
    if " and " in artist.lower():
        variants.append(_re.sub(r"\band\b", "&", artist, flags=_re.IGNORECASE))
    return list(dict.fromkeys(variants))  # deduplicate preserving order


def is_live_version(track) -> bool:
    """Return True if the track or its album title suggests a live recording."""
    keywords = ["live", "concert", "in concert", "live at", "live from", "mtv unplugged"]
    title = (track.title or "").lower()
    try:
        album_title = (track.album().title or "").lower()
    except Exception:
        album_title = ""
    # Also handle date patterns like (2005-06-22) typical in live bootlegs
    date_pattern = _re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")
    return (
        any(kw in title for kw in keywords)
        or any(kw in album_title for kw in keywords)
        or bool(date_pattern.search(title))
        or bool(date_pattern.search(album_title))
    )


def _no_consecutive_artists(tracks: list[Track]) -> list[Track]:
    """Reorder tracks so no two consecutive tracks share the same artist (best-effort)."""
    import heapq
    from collections import deque

    artist_map: dict[str, deque] = {}
    for t in tracks:
        key = t.artist.lower()
        artist_map.setdefault(key, deque()).append(t)

    heap = [(-len(v), k) for k, v in artist_map.items()]
    heapq.heapify(heap)

    result: list[Track] = []
    prev_key: str | None = None

    while heap:
        neg_cnt, key = heapq.heappop(heap)
        if key == prev_key and heap:
            neg_cnt2, key2 = heapq.heappop(heap)
            result.append(artist_map[key2].popleft())
            prev_key = key2
            if artist_map[key2]:
                heapq.heappush(heap, (-len(artist_map[key2]), key2))
            heapq.heappush(heap, (neg_cnt, key))
        else:
            result.append(artist_map[key].popleft())
            prev_key = key
            if artist_map[key]:
                heapq.heappush(heap, (-len(artist_map[key]), key))

    return result


def _diversify_tracks(tracks: list[Track], max_per_artist: int = 6) -> list[Track]:
    """Cap tracks per artist so the LLM prompt pool has broad variety."""
    counts: dict[str, int] = {}
    result = []
    for track in tracks:
        key = track.artist.lower()
        if counts.get(key, 0) < max_per_artist:
            result.append(track)
            counts[key] = counts.get(key, 0) + 1
    return result


def _apply_played_unplayed_split(tracks: list[Track], target: int) -> list[Track]:
    """Select *target* tracks with a 70/30 played-vs-unplayed balance.

    Preserves the relative ordering of *tracks* (e.g. ALS rank) within each
    bucket so the highest-relevance tracks are chosen first.
    """
    if len(tracks) <= target:
        return tracks

    played = [t for t in tracks if t.play_count > 0]
    unplayed = [t for t in tracks if t.play_count == 0]

    n_played = min(round(target * 0.7), len(played))
    n_unplayed = min(target - n_played, len(unplayed))

    # Fill shortfall from the other bucket
    shortage = target - n_played - n_unplayed
    if shortage > 0:
        if len(played) > n_played:
            n_played = min(n_played + shortage, len(played))
        elif len(unplayed) > n_unplayed:
            n_unplayed = min(n_unplayed + shortage, len(unplayed))

    # Take top-N from each bucket (preserving ALS order within each)
    selected_keys = {t.rating_key for t in played[:n_played]} | {t.rating_key for t in unplayed[:n_unplayed]}
    # Restore original relative order (ALS rank)
    return [t for t in tracks if t.rating_key in selected_keys]


def generate_narrative(
    track_selections: list[dict],
    llm_client,
    user_request: str = "",
) -> tuple[str, str]:
    """Generate a creative title and narrative for the playlist.

    Args:
        track_selections: List of track dicts with artist, title, album, reason
        llm_client: LLM client instance
        user_request: Original user prompt/request for context

    Returns:
        Tuple of (playlist_title with date, narrative)
        On failure, returns ("{Mon YYYY} Playlist", "")
    """
    # Build input for Query 2: track list with reasons
    tracks_with_reasons = "\n".join(
        f"- {sel.get('artist', 'Unknown')} - \"{sel.get('title', 'Unknown')}\": {sel.get('reason', 'Selected for this playlist')}"
        for sel in track_selections[:25]  # Include full 25-track playlist context
    )

    # Include user request for context
    if user_request:
        narrative_prompt = f"User's request: {user_request}\n\nSelected tracks:\n{tracks_with_reasons}"
    else:
        narrative_prompt = f"Selected tracks:\n{tracks_with_reasons}"

    # Get current month/year for title suffix
    date_suffix = datetime.now().strftime("%b %Y")
    fallback_title = f"{date_suffix} Playlist"

    try:
        # Use analysis model for better creative writing quality
        response = llm_client.analyze(narrative_prompt, NARRATIVE_SYSTEM)
        result = llm_client.parse_json_response(response)

        # Handle array-wrapped responses (some LLMs wrap in [])
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        if not isinstance(result, dict):
            logger.warning("Narrative response not a dict: %s", type(result).__name__)
            return fallback_title, ""

        raw_title = result.get("title", "").strip()

        # Try common alternate keys for narrative
        narrative = (
            result.get("narrative")
            or result.get("description")
            or result.get("text")
            or result.get("content")
            or ""
        ).strip()

        # Log if we got title but no narrative (helps debug)
        if raw_title and not narrative:
            logger.warning("Narrative missing from response. Keys: %s", list(result.keys()))

        # Append date to title
        if raw_title:
            playlist_title = f"{raw_title} - {date_suffix}"
        else:
            playlist_title = fallback_title

        return playlist_title, narrative

    except Exception as e:
        logger.warning("Narrative generation failed: %s", e)
        return fallback_title, ""


def _cached_track_to_model(cached: dict) -> Track:
    """Convert a cached track dict to a Track model."""
    gerbera_id = str(cached.get("gerbera_id") or cached.get("id") or "")
    return Track(
        rating_key=gerbera_id,
        title=cached["title"],
        artist=cached["artist"],
        album=cached["album"],
        duration_ms=cached.get("duration_ms") or 0,
        year=cached.get("year"),
        genres=cached.get("genres") or [],
        art_url="",
        play_count=cached.get("play_count") or 0,
    )


def _get_tracks_from_cache(
    genres: list[str] | None,
    decades: list[str] | None,
    exclude_live: bool,
    min_rating: int,
    max_tracks_to_ai: int,
) -> list[Track]:
    """Get tracks from local library cache.

    Returns:
        List of Track objects
    """
    effective_limit = max_tracks_to_ai if max_tracks_to_ai > 0 else 2000

    if library_cache.has_cached_tracks():
        logger.info("Using cached tracks for generation")
        cached_tracks = library_cache.get_tracks_by_filters(
            genres=genres,
            decades=decades,
            min_rating=min_rating,
            exclude_live=exclude_live,
            limit=effective_limit,
        )
        return [_cached_track_to_model(t) for t in cached_tracks]

    logger.warning("Library cache is empty — no tracks available")
    return []


def write_m3u(
    tracks: list[dict],
    playlist_title: str,
    output_dir: str,
    date_str: str | None = None,
) -> str:
    """Write an Extended M3U playlist file and return its path."""
    if date_str is None:
        date_str = _date.today().isoformat()
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


def build_track_prompt_entry(track: dict, favs: Favorites) -> str:
    """Format a track for the LLM prompt; append [FAVORITE] for preferred tracks."""
    genres_raw = track.get("genres", "[]")
    if isinstance(genres_raw, list):
        genres = genres_raw
    else:
        genres = _json.loads(genres_raw)
    genre_str = ", ".join(genres) if genres else "unknown"
    fav_tag = " [FAVORITE]" if is_favorite(favs, track.get("artist", ""), track.get("album")) else ""
    return (
        f"{track.get('artist', '')} — {track.get('title', '')} "
        f"({track.get('album', '')}, {track.get('year', '?')}, "
        f"Genre: {genre_str}, Plays: {track.get('play_count', 0)}){fav_tag}"
    )


def generate_playlist_stream(
    prompt: str | None = None,
    seed_track: Track | None = None,
    selected_dimensions: list[str] | None = None,
    additional_notes: str | None = None,
    refinement_answers: list[str | None] | None = None,
    genres: list[str] | None = None,
    decades: list[str] | None = None,
    track_count: int = 25,
    exclude_live: bool = True,
    min_rating: int = 0,
    max_tracks_to_ai: int = 500,
) -> Generator[str, None, None]:
    """Generate a playlist with streaming progress updates.

    Yields SSE-formatted events with progress updates and final result.
    """
    def emit(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        logger.info("Starting playlist generation (streaming)")
        llm_client = get_llm_client()

        if not llm_client:
            yield emit("error", {"message": "LLM client not initialized"})
            return

        has_filters = genres or decades or min_rating > 0

        # Step 1: Fetch tracks from local cache
        yield emit("progress", {"step": "fetching", "message": "Loading tracks from library cache..."})

        # Fetch a larger pool so diversity + weighted sampling have material to work with.
        # For high-context providers (Gemini) the pool equals the target; for others we
        # fetch up to 3x to give the two sampling passes room to operate.
        pool_size = max(max_tracks_to_ai, min(max_tracks_to_ai * 3, 3000))
        logger.info("Fetching tracks: genres=%s, decades=%s, min_rating=%s, pool_size=%s",
                    genres, decades, min_rating, pool_size)
        raw_pool = _get_tracks_from_cache(
            genres=genres,
            decades=decades,
            exclude_live=exclude_live,
            min_rating=min_rating,
            max_tracks_to_ai=pool_size,
        )

        if not raw_pool:
            yield emit("error", {"message": "No tracks match the selected filters. Try broadening your selection."})
            return

        # Apply artist diversity cap, then rank by ALS relevance (falls back
        # to play_count sort when the model is not yet trained).
        diverse_pool = _diversify_tracks(raw_pool, max_per_artist=6)
        seed_id = seed_track.rating_key if seed_track else None
        als_ranked = _als_recommender.rank(
            candidate_tracks=diverse_pool,
            seed_track_id=seed_id,
            n=max_tracks_to_ai,
        )
        filtered_tracks = _apply_played_unplayed_split(als_ranked, target=max_tracks_to_ai)

        logger.info(
            "Pool: %d raw → %d after diversity → %d after ALS rank → %d after 70/30 split",
            len(raw_pool), len(diverse_pool), len(als_ranked), len(filtered_tracks),
        )

        # Step 2: Report track count
        played_count = sum(1 for t in filtered_tracks if t.play_count > 0)
        unplayed_count = len(filtered_tracks) - played_count
        yield emit("progress", {
            "step": "filtering",
            "message": f"Using {len(filtered_tracks)} tracks ({played_count} played, {unplayed_count} unheard)…",
        })

        # Step 3: Build track list
        yield emit("progress", {"step": "preparing", "message": f"Preparing {len(filtered_tracks)} tracks for AI..."})

        # Load favorites for prompt boost (no-op if file missing or not configured)
        try:
            _favs = load_favorites()
        except Exception:
            _favs = Favorites()

        track_list = "\n".join(
            f"{i+1}. {build_track_prompt_entry(t.model_dump(), _favs)}"
            for i, t in enumerate(filtered_tracks)
        )

        # Load track feedback for prompt context
        try:
            _feedback_rows = library_cache.get_track_feedback()
            _feedback_block = _build_feedback_prompt(_feedback_rows)
        except Exception:
            _feedback_block = None

        # Build the generation prompt
        generation_parts = []

        if prompt:
            generation_parts.append(f"User's request: {prompt}")

        if seed_track:
            generation_parts.append(
                f"Seed track: {seed_track.title} by {seed_track.artist} "
                f"(from {seed_track.album}, {seed_track.year or 'Unknown year'})"
            )
            if selected_dimensions:
                generation_parts.append(f"Explore these dimensions: {', '.join(selected_dimensions)}")

        if additional_notes:
            generation_parts.append(f"Additional notes: {additional_notes}")

        if refinement_answers:
            answered = [a for a in refinement_answers if a]
            if answered:
                generation_parts.append(f"User preferences: {', '.join(answered)}")

        if _feedback_block:
            generation_parts.append(_feedback_block)

        generation_parts.append(
            f"\nThe tracks below are pre-ranked by relevance. "
            f"Select and reorder {track_count} for best flow and variety:\n{track_list}"
        )

        generation_prompt = "\n\n".join(generation_parts)

        # Step 4: Call LLM
        yield emit("progress", {"step": "ai_working", "message": "AI is curating your playlist..."})

        logger.info("Calling LLM with prompt length: %d chars", len(generation_prompt))
        response = llm_client.generate(generation_prompt, GENERATION_SYSTEM)
        logger.info("LLM response received: %d input, %d output tokens", response.input_tokens, response.output_tokens)

        # Step 5: Parse response
        yield emit("progress", {"step": "parsing", "message": "Parsing AI selections..."})

        track_selections = llm_client.parse_json_response(response)

        if not isinstance(track_selections, list):
            yield emit("error", {"message": "LLM returned invalid track selection format"})
            return

        # Step 6: Match tracks
        yield emit("progress", {"step": "matching", "message": f"Matching {len(track_selections)} selections to library..."})

        matched_tracks: list[Track] = []
        used_keys: set[str] = set()
        track_reasons: dict[str, str] = {}
        max_per_artist_final = 3
        artist_final_counts: dict[str, int] = {}

        if seed_track:
            used_keys.add(seed_track.rating_key)

        for selection in track_selections:
            if len(matched_tracks) >= track_count:
                break

            artist = selection.get("artist", "")
            title = selection.get("title", "")
            reason = selection.get("reason", "")

            for track in filtered_tracks:
                if track.rating_key in used_keys:
                    continue

                if _tracks_match(artist, title, track):
                    artist_key = track.artist.lower()
                    if artist_final_counts.get(artist_key, 0) < max_per_artist_final:
                        matched_tracks.append(track)
                        used_keys.add(track.rating_key)
                        artist_final_counts[artist_key] = artist_final_counts.get(artist_key, 0) + 1
                        if reason:
                            track_reasons[track.rating_key] = reason
                    break  # Match found; move on regardless of whether it was accepted

        matched_tracks = _no_consecutive_artists(matched_tracks)

        # Step 7: Generate narrative
        yield emit("progress", {"step": "narrative", "message": "Writing playlist narrative..."})

        playlist_title, narrative = generate_narrative(track_selections, llm_client, prompt or "")
        logger.info("Generated narrative: title='%s', narrative_len=%d", playlist_title, len(narrative))

        # Emit narrative event for frontend
        yield emit("narrative", {
            "playlist_title": playlist_title,
            "narrative": narrative,
            "track_reasons": track_reasons,
            "user_request": prompt or "",
        })

        # Step 8: Complete
        logger.info("Track matching complete. Matched %d tracks", len(matched_tracks))
        logger.info("Emitting 'Playlist ready!' progress event")
        yield emit("progress", {"step": "complete", "message": "Playlist ready!"})

        logger.info("Building GenerateResponse: tokens=%s, cost=%s",
                    getattr(response, 'total_tokens', 'N/A'),
                    response.estimated_cost() if response else 'N/A')

        try:
            result = GenerateResponse(
                tracks=matched_tracks,
                token_count=response.total_tokens,
                estimated_cost=response.estimated_cost(),
                playlist_title=playlist_title,
                narrative=narrative,
                track_reasons=track_reasons,
            )
            logger.info("GenerateResponse built successfully with %d tracks", len(result.tracks))
        except Exception as e:
            logger.exception("Failed to build GenerateResponse: %s", e)
            yield emit("error", {"message": f"Failed to build response: {e}"})
            return

        # Send tracks in batches to work around iOS Safari dropping large SSE events.
        # Safari Mobile has undocumented buffering limits that can cause large events
        # to be silently dropped. Batching keeps each event small (~2KB).
        tracks_data = [t.model_dump(mode="json") for t in result.tracks]
        batch_size = 5
        for i in range(0, len(tracks_data), batch_size):
            batch = tracks_data[i:i + batch_size]
            logger.info("Emitting track batch %d-%d", i, i + len(batch))
            yield emit("tracks", {"batch": batch, "index": i})

        # Save result to history before emitting the final event
        result_id = None
        try:
            result_type = "seed_playlist" if seed_track else "prompt_playlist"
            # Title: always use the LLM-generated playlist title
            result_title = playlist_title
            # Use first track's rating key for card thumbnail
            first_art_key = matched_tracks[0].rating_key if matched_tracks else None
            # Subtitle: seed playlists show origin track, prompt playlists show prompt + count
            if seed_track:
                result_subtitle = f"From: {seed_track.title} by {seed_track.artist} \u00b7 {len(matched_tracks)} tracks"
            elif prompt:
                result_subtitle = f"{prompt} \u00b7 {len(matched_tracks)} tracks"
            else:
                result_subtitle = f"{len(matched_tracks)} tracks"
            result_id = library_cache.save_result(
                result_type=result_type,
                title=result_title,
                prompt=prompt or "",
                snapshot=result.model_dump(mode="json"),
                track_count=len(matched_tracks),
                art_rating_key=first_art_key,
                subtitle=result_subtitle,
            )
        except Exception as e:
            logger.warning("Failed to save result: %s", e)

        # Emit small complete event with just metadata
        logger.info("Emitting complete event")
        complete_data = {
            "track_count": len(result.tracks),
            "token_count": result.token_count,
            "estimated_cost": result.estimated_cost,
            "playlist_title": result.playlist_title,
            "narrative": result.narrative,
            "track_reasons": result.track_reasons,
        }
        if result_id:
            complete_data["result_id"] = result_id
        yield emit("complete", complete_data)
        logger.info("Complete event emitted successfully")

        # Trailing padding to push complete event through network buffers (iOS Safari fix)
        # SSE comments (lines starting with ':') are ignored by the parser but help flush buffers
        yield ": heartbeat\n\n"

    except Exception as e:
        logger.exception("Error during playlist generation")
        yield emit("error", {"message": str(e)})


GENERATION_SYSTEM = """You are a music curator creating a playlist from a user's music library.

You will be given:
1. A description of what the user wants (prompt, seed track dimensions, or both)
2. A numbered list of tracks that are available in their library

The tracks below are pre-ranked by relevance; your task is to select and reorder for best flow and variety. For each track, include a brief reason (1 sentence) explaining why it fits.

Guidelines:
- Prefer tracks near the top of the list — they are already ranked by relevance to the user's taste and the seed track
- Vary the selection - don't pick too many tracks from the same artist or album
- Consider the flow of the playlist - how tracks will sound in sequence
- If using a seed track, don't include the seed track itself in the results

Return ONLY a JSON array like:
[
  {"artist": "Artist Name", "album": "Album Name", "title": "Track Title", "reason": "Brief explanation of why this track fits."},
  ...
]

No markdown formatting, no explanations - just the JSON array."""


NARRATIVE_SYSTEM = """You are a music connoisseur writing a brief liner note for a playlist.

Given the user's original request and the track selections (with reasons), create:
1. A creative playlist title (2-5 words, evocative, do NOT include any date)
2. A brief narrative (3 sentences, under 400 characters) that:
   - Reflects the mood or theme the user asked for
   - Mentions 3-4 specific songs by name (use single quotes around song names, e.g. 'Skinny Love')

Sound like a passionate music lover. Be concise.

Return ONLY valid JSON:
{"title": "Creative Title Here", "narrative": "Your brief narrative with 'song names' in single quotes..."}

No markdown formatting, no explanations - just the JSON object."""


def generate_favorites_playlist_stream(
    track_count: int = 30,
    max_tracks_to_ai: int = 500,
) -> Generator[str, None, None]:
    """Generate a playlist mixing favorites (~70%) with new library additions (~30%).

    Yields SSE-formatted events identical to generate_playlist_stream.
    """
    def emit(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        llm_client = get_llm_client()
        if not llm_client:
            yield emit("error", {"message": "LLM client not initialized"})
            return

        yield emit("progress", {"step": "fetching", "message": "Lade Favoriten aus der Bibliothek…"})

        # Load favorites
        try:
            favs = load_favorites()
        except Exception:
            favs = Favorites()

        if not favs.artists and not favs.albums:
            yield emit("error", {
                "message": "Keine Favoriten konfiguriert. Bitte erst Künstler oder Alben im Library-Tab als Favoriten markieren."
            })
            return

        # Fetch all non-live tracks and split by favorites
        all_tracks = library_cache.get_tracks_by_filters(exclude_live=True, limit=0)

        fav_tracks = [
            t for t in all_tracks
            if is_favorite(favs, t.get("artist", ""), t.get("album", ""))
        ]

        if not fav_tracks:
            yield emit("error", {"message": "Keine Tracks von Favoriten-Künstlern in der Bibliothek gefunden."})
            return

        # Get recently added non-favorite tracks
        new_candidates = library_cache.get_new_tracks(limit=400)
        new_tracks = [
            t for t in new_candidates
            if not is_favorite(favs, t.get("artist", ""), t.get("album", ""))
        ]

        # Fallback: unplayed non-favorites if not enough truly new tracks
        if len(new_tracks) < 30:
            other_tracks = [
                t for t in all_tracks
                if not is_favorite(favs, t.get("artist", ""), t.get("album", ""))
            ]
            known_new_ids = {t.get("gerbera_id") for t in new_tracks}
            unplayed = [
                t for t in other_tracks
                if t.get("play_count", 0) == 0 and t.get("gerbera_id") not in known_new_ids
            ]
            _random.shuffle(unplayed)
            new_tracks.extend(unplayed[:max(0, 100 - len(new_tracks))])

        yield emit("progress", {
            "step": "filtering",
            "message": f"{len(fav_tracks)} Favoriten-Tracks, {len(new_tracks)} neue Tracks gefunden.",
        })

        # Build curated pool: apply artist diversity cap on favorites, keep new tracks ordered by recency
        _random.shuffle(fav_tracks)
        fav_counts: dict[str, int] = {}
        fav_pool: list[dict] = []
        for t in fav_tracks:
            key = (t.get("artist") or "").lower()
            if fav_counts.get(key, 0) < 8:
                fav_pool.append(t)
                fav_counts[key] = fav_counts.get(key, 0) + 1

        # Trim pools so total fits in max_tracks_to_ai
        max_new = min(len(new_tracks), 200)
        max_fav = min(len(fav_pool), max_tracks_to_ai - max_new, 350)
        if len(fav_pool) > max_fav:
            fav_pool = _random.sample(fav_pool, max_fav)
        new_pool = new_tracks[:max_new]

        combined = fav_pool + new_pool
        fav_ids = {t.get("gerbera_id") for t in fav_pool}
        new_ids = {t.get("gerbera_id") for t in new_pool}

        # Build tagged track list for the LLM
        track_lines = []
        for i, track in enumerate(combined):
            gid = track.get("gerbera_id")
            genres_raw = track.get("genres", [])
            genres = genres_raw if isinstance(genres_raw, list) else _json.loads(genres_raw or "[]")
            genre_str = ", ".join(genres) if genres else "unknown"
            tag = " [FAVORITE]" if gid in fav_ids else (" [NEW]" if gid in new_ids else "")
            track_lines.append(
                f"{i + 1}. {track.get('artist', '')} — {track.get('title', '')} "
                f"({track.get('album', '')}, {track.get('year', '?')}, "
                f"Genre: {genre_str}, Plays: {track.get('play_count', 0)}){tag}"
            )

        # Load track feedback for prompt context
        try:
            _feedback_rows = library_cache.get_track_feedback()
            _feedback_block = _build_feedback_prompt(_feedback_rows)
        except Exception:
            _feedback_block = None

        n_fav = round(track_count * 0.7)
        n_new = track_count - n_fav
        _feedback_section = f"\n\n{_feedback_block}" if _feedback_block else ""
        generation_prompt = (
            f"Select {track_count} tracks: approximately {n_fav} from [FAVORITE] tracks "
            f"and approximately {n_new} from [NEW] tracks."
            f"{_feedback_section}\n\n"
            + "\n".join(track_lines)
        )

        yield emit("progress", {"step": "ai_working", "message": "KI stellt Favoriten-Mix zusammen…"})

        response = llm_client.generate(generation_prompt, FAVORITES_SYSTEM)
        logger.info("Favorites LLM response: %d input, %d output tokens",
                    response.input_tokens, response.output_tokens)

        yield emit("progress", {"step": "parsing", "message": "Auswahl wird verarbeitet…"})

        track_selections = llm_client.parse_json_response(response)
        if not isinstance(track_selections, list):
            yield emit("error", {"message": "LLM returned invalid format"})
            return

        yield emit("progress", {"step": "matching", "message": "Tracks werden abgeglichen…"})

        # Convert dicts to Track objects for fuzzy matching
        pool_as_tracks = [
            Track(
                rating_key=str(t.get("gerbera_id", "")),
                title=t.get("title", ""),
                artist=t.get("artist", ""),
                album=t.get("album", ""),
                duration_ms=t.get("duration_ms") or 0,
                year=t.get("year"),
                genres=t.get("genres", []) if isinstance(t.get("genres"), list) else [],
                art_url="",
                play_count=t.get("play_count") or 0,
            )
            for t in combined
        ]

        matched_tracks: list[Track] = []
        used_keys: set[str] = set()
        track_reasons: dict[str, str] = {}
        max_per_artist_final = 3
        artist_final_counts: dict[str, int] = {}

        for selection in track_selections:
            if len(matched_tracks) >= track_count:
                break
            sel_artist = selection.get("artist", "")
            sel_title = selection.get("title", "")
            reason = selection.get("reason", "")
            for track in pool_as_tracks:
                if track.rating_key in used_keys:
                    continue
                if _tracks_match(sel_artist, sel_title, track):
                    artist_key = track.artist.lower()
                    if artist_final_counts.get(artist_key, 0) < max_per_artist_final:
                        matched_tracks.append(track)
                        used_keys.add(track.rating_key)
                        artist_final_counts[artist_key] = artist_final_counts.get(artist_key, 0) + 1
                        if reason:
                            track_reasons[track.rating_key] = reason
                    break

        matched_tracks = _no_consecutive_artists(matched_tracks)

        yield emit("progress", {"step": "narrative", "message": "Playlist-Titel wird erstellt…"})

        playlist_title, narrative = generate_narrative(track_selections, llm_client, "Favoriten-Mix")

        yield emit("narrative", {
            "playlist_title": playlist_title,
            "narrative": narrative,
            "track_reasons": track_reasons,
            "user_request": "Favoriten-Mix",
        })

        yield emit("progress", {"step": "complete", "message": "Playlist bereit!"})

        try:
            result = GenerateResponse(
                tracks=matched_tracks,
                token_count=response.total_tokens,
                estimated_cost=response.estimated_cost(),
                playlist_title=playlist_title,
                narrative=narrative,
                track_reasons=track_reasons,
            )
        except Exception as e:
            logger.exception("Failed to build GenerateResponse: %s", e)
            yield emit("error", {"message": f"Failed to build response: {e}"})
            return

        tracks_data = [t.model_dump(mode="json") for t in result.tracks]
        for i in range(0, len(tracks_data), 5):
            yield emit("tracks", {"batch": tracks_data[i:i + 5], "index": i})

        result_id = None
        try:
            result_id = library_cache.save_result(
                result_type="favorites_playlist",
                title=playlist_title,
                prompt="Favoriten-Mix",
                snapshot=result.model_dump(mode="json"),
                track_count=len(matched_tracks),
                art_rating_key=matched_tracks[0].rating_key if matched_tracks else None,
                subtitle=f"Favoriten-Mix · {len(matched_tracks)} Tracks",
            )
        except Exception as e:
            logger.warning("Failed to save result: %s", e)

        complete_data: dict = {
            "track_count": len(result.tracks),
            "token_count": result.token_count,
            "estimated_cost": result.estimated_cost,
            "playlist_title": result.playlist_title,
            "narrative": result.narrative,
            "track_reasons": result.track_reasons,
        }
        if result_id:
            complete_data["result_id"] = result_id
        yield emit("complete", complete_data)
        yield ": heartbeat\n\n"

    except Exception as e:
        logger.exception("Error during favorites playlist generation")
        yield emit("error", {"message": str(e)})


FAVORITES_SYSTEM = """You are a music curator creating a personal "Favorites Mix" playlist.

The track list contains tracks tagged as:
- [FAVORITE] = from the user's favourite artists or albums
- [NEW] = recently added to the library, not yet heard much
- (no tag) = general library

Your task: select the requested number of tracks forming a cohesive mix where:
- Approximately 70% are [FAVORITE] tracks (the familiar, beloved core)
- Approximately 30% are [NEW] tracks that complement the favourites in style, mood, or era

Guidelines:
- Choose [NEW] tracks that feel like natural companions to the [FAVORITE] tracks
- Vary artists — do not pick too many tracks from the same artist
- The [NEW] tracks should feel like exciting discoveries that fit the musical DNA of the favourites
- Consider the flow of the playlist as a whole

Return ONLY a JSON array:
[
  {"artist": "Artist Name", "title": "Track Title", "reason": "One sentence why it fits."},
  ...
]

No markdown, no explanations — just the JSON array."""


def _tracks_match(llm_artist: str, llm_title: str, library_track: Track) -> bool:
    """Check if LLM selection matches a library track.

    Uses token_sort_ratio so word-order differences (e.g. "The Beatles" vs
    "Beatles") and common 'The' prefixes don't cause misses.
    Threshold is 72 — permissive enough to catch close variants, strict
    enough to avoid cross-artist false positives.
    """
    from rapidfuzz import fuzz

    simplified_llm_title = simplify_string(llm_title)
    simplified_lib_title = simplify_string(library_track.title)

    if fuzz.token_sort_ratio(simplified_llm_title, simplified_lib_title) < FUZZ_THRESHOLD:
        return False

    for artist_variant in normalize_artist(llm_artist):
        simplified_artist = simplify_string(artist_variant)
        simplified_lib_artist = simplify_string(library_track.artist)
        if fuzz.token_sort_ratio(simplified_artist, simplified_lib_artist) >= FUZZ_THRESHOLD:
            return True

    return False
