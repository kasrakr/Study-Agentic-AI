from app.llm import get_chat_model
from app.rag.embeddings import get_embeddings


def test_embeddings_use_configured_model_and_avoid_tiktoken_download(settings):
    emb = get_embeddings(settings)
    assert emb.model == settings.openai_embedding_model
    assert emb.check_embedding_ctx_length is False  # no hidden second network host
    assert emb.openai_api_base == "https://api.gapgpt.app/v1"
    assert emb.max_retries == 0  # retries are handled by app.resilience.call_openai


def test_chat_model_is_configured_centrally(settings):
    chat = get_chat_model(settings, temperature=0.2)
    assert chat.model_name == settings.openai_chat_model
    assert chat.temperature == 0.2 and chat.max_retries == 0
    assert chat.openai_api_base == "https://api.gapgpt.app/v1"


def test_base_url_is_configurable_and_normalised(settings):
    s = settings.model_copy(update={"openai_base_url": "https://api.openai.com/v1"})
    assert get_chat_model(s).openai_api_base == "https://api.openai.com/v1"
    assert get_embeddings(s).openai_api_base == "https://api.openai.com/v1"


def test_temperature_omitted_for_reasoning_model_families(settings):
    s = settings.model_copy(update={"openai_chat_model": "o3-mini"})
    assert get_chat_model(s, temperature=0.2).temperature is None
