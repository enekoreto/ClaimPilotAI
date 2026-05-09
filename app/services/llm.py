from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.config import Settings, get_settings


def build_chat_model(settings: Settings | None = None) -> BaseChatModel | None:
    """Return a configured chat model when API credentials are available.

    The application defaults to deterministic services for reliability in tests and demos.
    Set LLM_PROVIDER=openai or azure_openai to enable this in future node variants.
    """
    settings = settings or get_settings()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    if (
        settings.llm_provider == "azure_openai"
        and settings.azure_openai_api_key
        and settings.azure_openai_endpoint
        and settings.azure_openai_deployment
    ):
        return AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version="2024-02-15-preview",
            temperature=0,
        )
    return None
