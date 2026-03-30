import tempfile, os
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
