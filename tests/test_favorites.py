import tempfile, os
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

def test_empty_yaml_returns_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        path = f.name
    try:
        favs = load_favorites(path)
        assert is_favorite(favs, artist="Anyone") is False
    finally:
        os.unlink(path)
