import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_placeholder_secrets() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(app_env="production")


def test_production_accepts_strong_secrets() -> None:
    settings = Settings(app_env="production", secret_key="a" * 40, contact_hash_key="b" * 40)
    assert settings.cookie_secure


def test_invalid_generator_fails_clearly() -> None:
    with pytest.raises(ValidationError, match="answer_generator"):
        Settings(answer_generator="gpt-magico")


def test_development_cookies_not_secure() -> None:
    assert not Settings(app_env="development").cookie_secure
