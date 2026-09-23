import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_are_phase1_only():
    settings = Settings(_env_file=None)
    assert settings.ekt_mode == "mock"
    assert settings.ekt_base_url == "https://ekt.kz"
    assert settings.ekt_product_detail_path == "/api/products/detail"
    assert set(Settings.model_fields) == {
        "ekt_mode", "ekt_base_url", "ekt_product_detail_path",
        "ekt_timeout_seconds", "max_upstream_response_bytes",
    }


def test_environment_and_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("EKT_MODE=live\nEKT_TIMEOUT_SECONDS=4\n", encoding="utf-8")
    monkeypatch.setenv("EKT_TIMEOUT_SECONDS", "2")
    settings = Settings(_env_file=env)
    assert settings.ekt_mode == "live"
    assert settings.ekt_timeout_seconds == 2


@pytest.mark.parametrize("changes", [
    {"ekt_mode": "automatic"},
    {"ekt_timeout_seconds": 0},
    {"ekt_timeout_seconds": -1},
    {"ekt_timeout_seconds": 61},
    {"ekt_timeout_seconds": float("nan")},
    {"ekt_timeout_seconds": float("inf")},
    {"max_upstream_response_bytes": 0},
    {"max_upstream_response_bytes": 20_000_000},
])
def test_invalid_limits_or_mode_fail_startup(changes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


@pytest.mark.parametrize("path", [
    "https://other.invalid/detail", "//other.invalid/detail", "detail",
    "/api/../detail", "/api/./detail", "/api//detail", "/api/%2Fdetail",
    "/api/detail?id=1", "/api/detail#fragment", "/api/\\detail", "", "/api/detail\n",
])
def test_untrusted_paths_rejected(path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ekt_product_detail_path=path)


@pytest.mark.parametrize("origin", [
    "ftp://ekt.kz", "http://ekt.kz", "https://user:password@ekt.kz",
    "https://ekt.kz/catalog", "https://ekt.kz?key=secret", "https://ekt.kz#x",
    "https://", "https://ekt.kz:99999", "https://ekt.kz\\other", "https://ekt.kz\n",
])
def test_invalid_origins_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ekt_base_url=origin)


@pytest.mark.parametrize("origin", ["http://localhost:8080", "http://127.0.0.1", "http://[::1]:8080"])
def test_local_http_is_allowed(origin):
    assert Settings(_env_file=None, ekt_base_url=origin).ekt_base_url == origin


def test_origin_normalization_and_settings_are_immutable():
    settings = Settings(_env_file=None, ekt_base_url="https://ekt.kz/")
    assert settings.ekt_base_url == "https://ekt.kz"
    with pytest.raises(ValidationError):
        settings.ekt_product_detail_path = "//attacker.invalid/detail"
