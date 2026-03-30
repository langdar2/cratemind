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
        'INSERT INTO grb_playstatus ("group", item_id, playCount) VALUES (\'default\', 1, 7)'
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
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_test_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO mt_cds_object (id, ref_id, upnp_class, dc_title, location)
            VALUES (2, 1, 'object.item.audioItem.musicTrack', 'So What (copy)', '/music/copy.flac')
        """)
        conn.commit()
        conn.close()
        tracks = read_tracks(db_path)
        assert len(tracks) == 1
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
