import pytest

from app.config import PROJECT_ROOT, ConfigurationError, Settings


def _settings(**kw):
    return Settings(_env_file=None, **kw)


def test_missing_api_key_fails_startup_validation():
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        _settings().validate_for_startup()


def test_blank_api_key_counts_as_missing():
    s = _settings(openai_api_key="   ")
    assert not s.openai_configured


def test_overlap_must_be_smaller_than_chunk_size():
    s = _settings(openai_api_key="sk-x" * 5, chunk_size=200, chunk_overlap=200)
    with pytest.raises(ConfigurationError, match="CHUNK_OVERLAP"):
        s.validate_for_startup()


def test_valid_config_passes():
    _settings(openai_api_key="sk-test-123456").validate_for_startup()


def test_api_key_not_exposed_in_repr():
    s = _settings(openai_api_key="sk-super-secret-value")
    assert "sk-super-secret-value" not in repr(s)
    assert "sk-super-secret-value" not in str(s.model_dump())


def test_relative_paths_resolve_against_repo_root():
    s = _settings(upload_directory="storage/uploads", database_url="sqlite:///storage/x.db")
    assert s.upload_path == PROJECT_ROOT / "storage" / "uploads"
    assert s.sqlalchemy_url == f"sqlite:///{PROJECT_ROOT / 'storage' / 'x.db'}"


def test_cors_origins_parsed_from_comma_list():
    s = _settings(cors_origins="http://a.test, http://b.test ,")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
