"""
Extraction and synthesis agents implemented as lazy, cached factories.

Lazy initialization guarantees agents are constructed only AFTER secret loading
(keyring, .env, vault) has occurred, avoiding startup exceptions.
lru_cache avoids recreating models during iterative executions in the same process.
"""

from __future__ import annotations

import functools
import os

from pydantic_ai import Agent

from clashpy.core.models import ArgumentationFramework, FullAnalysisResult


def _resolve_model(model_name: str):
    """
    Resolves string identifiers into pydantic-ai Model instances.

    Supports:
    - Google Gemini: 'google:gemini-2.5-flash', 'gemini-2.5-flash'
    - Qwen via OpenRouter: 'openrouter:qwen/qwen-2.5-72b-instruct', 'qwen-72b', 'qwen-plus'
    - Qwen via Groq: 'groq:qwen-2.5-32b', 'groq:qwen/qwen-2.5-72b-instruct'
    - Qwen via DeepInfra: 'deepinfra:Qwen/Qwen2.5-72B-Instruct'
    - Qwen via Together AI: 'together:Qwen/Qwen2.5-72B-Instruct-Turbo'
    - Qwen via Alibaba DashScope: 'dashscope:qwen-plus', 'dashscope:qwen-turbo', 'dashscope:qwen-max'
    - Local / Offline: 'ollama:qwen2.5:7b', 'lmstudio:qwen2.5-7b'
    - OpenAI, Anthropic, Mistral, Groq native strings
    """
    model_lower = model_name.lower().strip()

    # Google Gemini shortcuts
    if model_name.startswith("gemini-"):
        from pydantic_ai.models.google import GoogleModel
        return GoogleModel(model_name)

    # Local LM Studio
    if model_name.startswith("lmstudio:"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        raw_name = model_name.split(":", 1)[1] or "local-model"
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            base_url = base_url.rstrip("/") + "/v1"

        provider = OpenAIProvider(base_url=base_url, api_key="not-needed")
        return OpenAIChatModel(raw_name, provider=provider)

    # Qwen Cloud / Alibaba DashScope (Compatible OpenAI Endpoint)
    if (
        model_name.startswith("qwencloud:")
        or model_name.startswith("qwen:")
        or model_name.startswith("dashscope:")
        or model_name.startswith("alicloud:")
        or model_name.startswith("alibaba:")
    ):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        raw_name = model_name.split(":", 1)[1] if ":" in model_name else "qwen-plus"
        if not raw_name or raw_name.lower() in ("default", "qwen", "cloud"):
            raw_name = "qwen-plus"

        api_key = (
            os.getenv("QWEN_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("ALICLOUD_API_KEY")
            or os.getenv("ALIBABA_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or "sk-placeholder"
        )
        base_url = os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(raw_name, provider=provider)

    # Qwen via DeepInfra (extremely cheap: ~$0.13 / 1M tokens)
    if model_name.startswith("deepinfra:"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        raw_name = model_name.split(":", 1)[1]
        api_key = os.getenv("DEEPINFRA_API_KEY") or os.getenv("DEEPINFRA_TOKEN") or "sk-placeholder"
        base_url = "https://api.deepinfra.com/v1/openai"
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(raw_name, provider=provider)

    # Qwen shortcuts (e.g. --model qwen-72b or --model qwen-plus or --model qwen-flash)
    if model_lower in ("qwen", "qwen-72b", "qwen-2.5-72b", "qwen-turbo", "qwen-plus"):
        # Auto-detect best available provider for Qwen:
        # 1. Groq (fast & affordable)
        # 2. DeepInfra (ultra-cheap ~$0.13/M)
        # 3. OpenRouter
        # 4. DashScope
        if os.getenv("GROQ_API_KEY"):
            return "groq:qwen-2.5-32b"
        if os.getenv("DEEPINFRA_API_KEY"):
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider
            provider = OpenAIProvider(base_url="https://api.deepinfra.com/v1/openai", api_key=os.environ["DEEPINFRA_API_KEY"])
            return OpenAIChatModel("Qwen/Qwen2.5-72B-Instruct", provider=provider)
        if os.getenv("OPENROUTER_API_KEY"):
            return "openrouter:qwen/qwen-2.5-72b-instruct"
        if os.getenv("DASHSCOPE_API_KEY"):
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider
            provider = OpenAIProvider(base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1", api_key=os.environ["DASHSCOPE_API_KEY"])
            return OpenAIChatModel("qwen-plus", provider=provider)

        # Default fallback to OpenRouter identifier
        return "openrouter:qwen/qwen-2.5-72b-instruct"

    return model_name


@functools.lru_cache(maxsize=4)
def get_extraction_agent(model_name: str) -> Agent[None, ArgumentationFramework]:
    model = _resolve_model(model_name)

    return Agent(
        model,
        output_type=ArgumentationFramework,
        system_prompt=(
            "Du bist Experte für Dungs Argumentation Frameworks. "
            "Analysiere die gelieferten Nachrichten zu genau einem Thema. "
            "Extrahiere möglichst viele klar unterscheidbare Argumente, "
            "idealerweise 15 bis 30. IDs strikt A1, A2, A3 ... . "
            "Erlaube echte gegenseitige Angriffe A<->B, wenn diese aus dem "
            "Material hervorgehen. "
            "source_url MUSS die exakte URL des konkreten Artikels sein, "
            "aus dem das Argument stammt. "
            "Wenn keine konkrete Zuordnung möglich ist: KEINE_QUELLE. "
            "Keine erfundenen Quellen. "
            "Formuliere auf Deutsch."
        ),
    )


def get_synthesis_agent(model_name: str) -> Agent[None, FullAnalysisResult]:
    model = _resolve_model(model_name)

    return Agent(
        model,
        output_type=FullAnalysisResult,
        system_prompt=(
            "Du erhältst ein Argumentationsframework und mathematisch "
            "berechnete Perspektiven. Formuliere für jede Perspektive eine "
            "kurze, sachliche übergeordnete These und einen Titel mit maximal "
            "vier Wörtern. Keine Bewertung oder Rangfolge der Perspektiven. "
            "Formuliere auf Deutsch."
        ),
    )
