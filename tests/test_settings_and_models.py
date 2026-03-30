from models import IngredientItem, RetrievedRecipe, RetrievalStrategy, RetrievalUpdateData
from settings import AppSettings


def test_settings_flags_without_optional_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BING_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("XHS_COOKIE", raising=False)
    monkeypatch.delenv("A1", raising=False)

    settings = AppSettings(_env_file=None)

    assert settings.openai_enabled is False
    assert settings.bing_enabled is False
    assert settings.mcp_enabled is False


def test_settings_flags_treat_whitespace_credentials_as_disabled(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    monkeypatch.setenv("BING_SEARCH_API_KEY", "\t")
    monkeypatch.setenv("XHS_COOKIE", "cookie")
    monkeypatch.setenv("A1", " ")

    settings = AppSettings(_env_file=None)

    assert settings.openai_enabled is False
    assert settings.gemini_enabled is False
    assert settings.bing_enabled is False
    assert settings.mcp_enabled is False


def test_settings_flags_enable_gemini_when_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "real-key")

    settings = AppSettings(_env_file=None)

    assert settings.gemini_enabled is True


def test_retrieval_update_payload_keeps_strategy_and_message():
    payload = RetrievalUpdateData(
        query="potato eggplant less-oil",
        status="success",
        strategy="Schema",
        title="Lightly Fried Eggplant and Potato",
        message="schema hit",
    )

    assert payload.strategy == "Schema"
    assert payload.title == "Lightly Fried Eggplant and Potato"
    assert payload.message == "schema hit"


def test_ingredient_item_preserves_quantity_text():
    item = IngredientItem(name="tomato", quantity="3 pcs (~450g)")
    assert item.quantity == "3 pcs (~450g)"


def test_retrieved_recipe_source_strategy_serializes_for_frontend():
    recipe = RetrievedRecipe(
        source_query="tomato soup",
        source_strategy=RetrievalStrategy.SCHEMA,
        title="Quick Tomato Soup",
    )

    dumped = recipe.model_dump()
    assert dumped["source_strategy"] == "Schema"
