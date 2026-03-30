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
    """'MM:SS' or 'H:MM:SS' → milliseconds"""
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
    """Read all audio tracks from Gerbera's SQLite database."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT
            o.id,
            o.dc_title,
            o.location,
            r.duration,
            COALESCE(ps.play_count, 0) AS play_count,
            MAX(CASE WHEN m.property_name = 'upnp:artist' THEN m.property_value END) AS artist,
            MAX(CASE WHEN m.property_name = 'upnp:album'  THEN m.property_value END) AS album,
            MAX(CASE WHEN m.property_name = 'upnp:genre'  THEN m.property_value END) AS genre,
            MAX(CASE WHEN m.property_name = 'dc:date'     THEN m.property_value END) AS year_str
        FROM mt_cds_object o
        LEFT JOIN mt_metadata       m  ON m.item_id  = o.id
        LEFT JOIN grb_cds_resource  r  ON r.item_id  = o.id AND r.res_id = 0
        LEFT JOIN (
            SELECT item_id, SUM(playCount) AS play_count
            FROM grb_playstatus
            GROUP BY item_id
        ) ps ON ps.item_id = o.id
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
