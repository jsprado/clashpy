"""
Extraction and synthesis agents implemented as lazy, cached factories.

Lazy initialization guarantees agents are constructed only AFTER secret loading
(keyring, .env, vault) has occurred, avoiding startup exceptions.
lru_cache avoids recreating models during iterative executions in the same process.
"""

from __future__ import annotations

import functools

from pydantic_ai import Agent

from argument_inferencer.core.models import ArgumentationFramework, FullAnalysisResult


@functools.lru_cache(maxsize=4)
def get_extraction_agent(model_name: str) -> Agent[None, ArgumentationFramework]:
    if model_name.startswith("gemini-"):
        from pydantic_ai.models.google import GoogleModel
        model = GoogleModel(model_name)
    elif model_name.startswith("lmstudio:"):
        from pydantic_ai.models.openai import OpenAIModel
        import os
        raw_name = model_name.split(":", 1)[1] or "local-model"
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = OpenAIModel(raw_name, base_url=base_url, api_key="not-needed")
    else:
        model = model_name

    return Agent(
        model,
        output_type=ArgumentationFramework,
        system_prompt=(
            "Du bist Experte für Dungs Argumentation Frameworks. "
            "Analysiere die gelieferten Nachrichten zu genau einem Thema. "
            "Extrahiere möglichst viele klar unterscheidbare Argumente, "
            "idealerweise 25 bis 40. IDs strikt A1, A2, A3 ... . "
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
    if model_name.startswith("gemini-"):
        from pydantic_ai.models.google import GoogleModel
        model = GoogleModel(model_name)
    elif model_name.startswith("lmstudio:"):
        from pydantic_ai.models.openai import OpenAIModel
        import os
        raw_name = model_name.split(":", 1)[1] or "local-model"
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = OpenAIModel(raw_name, base_url=base_url, api_key="not-needed")
    else:
        model = model_name

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
