"""Tests for API endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.models import DefaultsConfig


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    # Import here to avoid module-level import issues
    from backend.main import app
    return TestClient(app)


def create_mock_config(
    plex_url="http://test:32400",
    plex_token="token",
    music_library="Music",
    llm_provider="anthropic",
    llm_api_key="key",
    model_analysis="claude-sonnet-4-5",
    model_generation="claude-haiku-4-5",
    track_count=25,
    ollama_url="http://localhost:11434",
    custom_url="",
    custom_context_window=32768,
):
    """Create a properly structured mock config."""
    mock = MagicMock()
    mock.gerbera.db_path = ""
    mock.gerbera.playlist_output_dir = "/tmp"
    mock.gerbera.favorites_file = "favorites.yaml"
    mock.llm.provider = llm_provider
    mock.llm.api_key = llm_api_key
    mock.llm.model_analysis = model_analysis
    mock.llm.model_generation = model_generation
    mock.llm.ollama_url = ollama_url
    mock.llm.custom_url = custom_url
    mock.llm.custom_context_window = custom_context_window
    mock.defaults = DefaultsConfig(track_count=track_count)
    return mock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_status(self, client):
        """Should return health status."""
        with patch("backend.main.get_config") as mock_config:
            mock_config.return_value = create_mock_config()

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"

    def test_health_check_shows_plex_status(self, client):
        """Should show plex_connected field (always False in Gerbera mode)."""
        with patch("backend.main.get_config") as mock_config:
            mock_config.return_value = create_mock_config()

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert "plex_connected" in data
            assert data["plex_connected"] is False

    def test_health_check_shows_llm_status(self, client):
        """Should show LLM configuration status."""
        with patch("backend.main.get_config") as mock_config:
            mock_config.return_value = create_mock_config(llm_api_key="key")

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert "llm_configured" in data
            assert data["llm_configured"] is True


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_config_returns_safe_values(self, client):
        """GET /api/config should return config without secrets."""
        with patch("backend.main.get_config") as mock_get_config:
            mock_get_config.return_value = create_mock_config(
                llm_provider="anthropic",
                llm_api_key="secret-api-key",
            )

            response = client.get("/api/config")

            assert response.status_code == 200
            data = response.json()

            # Should show provider but not API key
            assert data["llm_provider"] == "anthropic"
            assert "api_key" not in data
            assert "secret-api-key" not in str(data)

    def test_post_config_validates_plex_url(self, client):
        """POST /api/config should succeed for valid updates."""
        with patch("backend.main.update_config_values") as mock_update:
            mock_config = create_mock_config()
            mock_update.return_value = mock_config

            response = client.post(
                "/api/config",
                json={"llm_provider": "openai"}
            )

            assert response.status_code == 200

    def test_post_config_updates_llm_provider(self, client):
        """POST /api/config should allow changing LLM provider."""
        with patch("backend.main.update_config_values") as mock_update:
            mock_config = create_mock_config(llm_provider="openai")
            mock_update.return_value = mock_config

            response = client.post(
                "/api/config",
                json={"llm_provider": "openai"}
            )

            assert response.status_code == 200


class TestIndexPage:
    """Tests for index page serving."""

    def test_index_returns_response(self, client):
        """Should return some response for root path."""
        response = client.get("/")
        # Either returns HTML or JSON message
        assert response.status_code == 200


class TestOllamaEndpoints:
    """Tests for Ollama API endpoints."""

    def test_ollama_status_connected(self, client):
        """GET /api/ollama/status should return connected status."""
        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.get_ollama_status") as mock_status:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_status.return_value = MagicMock(
                    connected=True,
                    model_count=3,
                    error=None,
                )

                response = client.get("/api/ollama/status")

                assert response.status_code == 200
                data = response.json()
                assert data["connected"] is True
                assert data["model_count"] == 3

    def test_ollama_status_not_connected(self, client):
        """GET /api/ollama/status should return error when not connected."""
        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.get_ollama_status") as mock_status:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_status.return_value = MagicMock(
                    connected=False,
                    model_count=0,
                    error="Connection refused",
                )

                response = client.get("/api/ollama/status")

                assert response.status_code == 200
                data = response.json()
                assert data["connected"] is False
                assert data["error"] == "Connection refused"

    def test_ollama_models_list(self, client):
        """GET /api/ollama/models should return list of models."""
        from backend.models import OllamaModel, OllamaModelsResponse

        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.list_ollama_models") as mock_models:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_models.return_value = OllamaModelsResponse(
                    models=[
                        OllamaModel(name="llama3:8b", size=4661224676, modified_at="2024-01-15T00:00:00Z"),
                        OllamaModel(name="mistral:latest", size=3825819904, modified_at="2024-01-14T00:00:00Z"),
                    ],
                    error=None,
                )

                response = client.get("/api/ollama/models")

                assert response.status_code == 200
                data = response.json()
                assert len(data["models"]) == 2
                assert data["models"][0]["name"] == "llama3:8b"

    def test_ollama_model_info(self, client):
        """GET /api/ollama/model-info should return model details."""
        from backend.models import OllamaModelInfo

        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.get_ollama_model_info") as mock_info:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_info.return_value = OllamaModelInfo(
                    name="llama3:8b",
                    context_window=8192,
                    parameter_size="8B",
                )

                response = client.get("/api/ollama/model-info?model=llama3:8b")

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "llama3:8b"
                assert data["context_window"] == 8192

    def test_ollama_model_info_not_found(self, client):
        """GET /api/ollama/model-info should return 404 for unknown model."""
        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.get_ollama_model_info") as mock_info:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_info.return_value = None  # Model not found

                response = client.get("/api/ollama/model-info?model=nonexistent")

                assert response.status_code == 404

    def test_ollama_status_with_custom_url(self, client):
        """GET /api/ollama/status should accept custom URL parameter."""
        with patch("backend.main.get_config") as mock_config:
            with patch("backend.main.get_ollama_status") as mock_status:
                mock_config.return_value = create_mock_config(
                    llm_provider="ollama",
                    ollama_url="http://localhost:11434",
                )
                mock_status.return_value = MagicMock(
                    connected=True,
                    model_count=1,
                    error=None,
                )

                response = client.get("/api/ollama/status?url=http://custom-host:11434")

                assert response.status_code == 200
                # Verify the custom URL was passed
                mock_status.assert_called_once_with("http://custom-host:11434")


def test_get_library_artists_returns_list(client):
    with patch("backend.library_cache.get_artists_with_stats", return_value=[
        {"artist": "Radiohead", "track_count": 47, "is_new": False, "is_favorite": True},
    ]):
        response = client.get("/api/library/artists")
        assert response.status_code == 200
        data = response.json()
        assert "artists" in data
        assert data["artists"][0]["artist"] == "Radiohead"
        assert data["artists"][0]["is_favorite"] is True


def test_get_library_albums_returns_list(client):
    with patch("backend.library_cache.get_albums_with_stats", return_value=[
        {"artist": "Radiohead", "album": "OK Computer", "track_count": 12, "is_new": True, "is_favorite": False},
    ]):
        response = client.get("/api/library/albums")
        assert response.status_code == 200
        data = response.json()
        assert "albums" in data
        assert data["albums"][0]["album"] == "OK Computer"


def test_toggle_favorite_returns_state(client):
    with patch("backend.library_cache.toggle_favorite", return_value=True):
        response = client.post("/api/favorites/toggle", json={"type": "artist", "artist": "Radiohead", "album": ""})
        assert response.status_code == 200
        assert response.json() == {"is_favorite": True}
