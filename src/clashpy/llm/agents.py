"""
Extraction and synthesis agents implemented as lazy, cached factories.

Lazy initialization guarantees agents are constructed only AFTER secret loading
(keyring, .env, vault) has occurred, avoiding startup exceptions.
lru_cache avoids recreating models during iterative executions in the same process.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import functools
import os
import re

from pydantic_ai import Agent

from clashpy.core.models import (
    Argument,
    ArgumentationFramework,
    ArgumentList,
    Attack,
    AttackList,
    FullAnalysisResult,
)


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

    # Apple Silicon (M-Series / Metal) / Local Ollama shortcuts
    if (
        model_name.startswith("ollama:")
        or model_lower in ("ollama", "local", "apple", "apple-silicon", "m4", "m3", "m2", "m1", "offline")
    ):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        if ":" in model_name:
            raw_name = model_name.split(":", 1)[1]
        else:
            raw_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            base_url = base_url.rstrip("/") + "/v1"

        provider = OpenAIProvider(base_url=base_url, api_key="ollama")
        return OpenAIChatModel(raw_name, provider=provider)

    # Apple MLX local server
    if model_name.startswith("mlx:"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        raw_name = model_name.split(":", 1)[1] or "mlx-model"
        base_url = os.getenv("MLX_BASE_URL", "http://localhost:8080/v1")
        provider = OpenAIProvider(base_url=base_url, api_key="not-needed")
        return OpenAIChatModel(raw_name, provider=provider)

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
def get_pro_agent(model_name: str) -> Agent[None, ArgumentList]:
    """Advocatus Agent: Specialized in identifying supportive arguments, benefits, and evidence."""
    model = _resolve_model(model_name)
    return Agent(
        model,
        output_type=ArgumentList,
        system_prompt=(
            "Du bist der 'Advocatus' (Pro-Perspektiven-Analyst).\n"
            "Deine Aufgabe: Untersuche den bereitgestellten Quellenkorpus gezielt nach Argumenten, "
            "die FÜR das angegebene Thema sprechen (Chancen, gesellschaftlicher Nutzen, Effizienzgewinne, "
            "positive Studienergebnisse, Vorteile, Innovationen).\n\n"
            "Regeln:\n"
            "1. Extrahiere 6 bis 15 distinkte, prägnante Pro-Thesen.\n"
            "2. Formuliere jede Behauptung (claim) präzise in 1–2 Sätzen auf Deutsch.\n"
            "3. Trage als 'source_url' die exakte URL des zugehörigen Quellartikels ein (oder KEINE_QUELLE).\n"
            "4. Vergib vorläufige IDs: P1, P2, P3 ...\n"
            "5. AUSSCHLIESSLICH DEUTSCH."
        ),
    )


@functools.lru_cache(maxsize=4)
def get_contra_agent(model_name: str) -> Agent[None, ArgumentList]:
    """Skeptiker Agent: Specialized in identifying counterarguments, risks, and critical constraints."""
    model = _resolve_model(model_name)
    return Agent(
        model,
        output_type=ArgumentList,
        system_prompt=(
            "Du bist der 'Skeptiker' (Contra-Perspektiven-Analyst).\n"
            "Deine Aufgabe: Untersuche den bereitgestellten Quellenkorpus gezielt nach Argumenten, "
            "die GEGEN das angegebene Thema sprechen (Risiken, finanzielle/ökonomische Kosten, "
            "Umsetzungshürden, Gegenstudien, ethische/rechtliche Bedenken, Verlierer).\n\n"
            "Regeln:\n"
            "1. Extrahiere 6 bis 15 distinkte, prägnante Contra-Thesen.\n"
            "2. Formuliere jede Behauptung (claim) präzise in 1–2 Sätzen auf Deutsch.\n"
            "3. Trage als 'source_url' die exakte URL des zugehörigen Quellartikels ein (oder KEINE_QUELLE).\n"
            "4. Vergib vorläufige IDs: C1, C2, C3 ...\n"
            "5. AUSSCHLIESSLICH DEUTSCH."
        ),
    )


@functools.lru_cache(maxsize=4)
def get_cross_examiner_agent(model_name: str) -> Agent[None, AttackList]:
    """Cross-Examiner Agent: Analyzes the unified argument pool to construct valid Dung attack relations."""
    model = _resolve_model(model_name)
    return Agent(
        model,
        output_type=AttackList,
        system_prompt=(
            "Du bist der 'Cross-Examiner' (formaler Inferenz- und Widerlegungs-Experte für Dungs Argumentation Frameworks).\n"
            "Du erhältst eine durchnummerierte Liste aller identifizierten Pro- und Contra-Argumente (A1, A2, A3...).\n"
            "Deine Aufgabe: Finde alle echten, logischen Angriffs- und Konfliktrelationen (Attacks) zwischen diesen Argumenten.\n\n"
            "Strikte Inferenzregeln:\n"
            "1. Ein gerichteter Angriff (A -> B) existiert GENAU DANN, wenn Argument A die Prämisse, Gültigkeit oder Wirksamkeit von Argument B direkt logisch angreift, widerlegt, einschränkt oder als Fehlschluss entlarvt.\n"
            "2. DILEMMA-ACHSEN: Wenn zwei Argumente in direktem, unlösbarem Zielkonflikt zueinander stehen, generiere ZWEI Angriffe (A -> B UND B -> A: wechselseitiger Angriff).\n"
            "3. IDs: Verwende AUSSCHLIESSLICH die exakten IDs aus der Argumentenliste (z. B. attacker_id='A2', target_id='A1'). Keine erfundenen IDs.\n"
            "4. Begründe jeden Angriff prägnant in 1 kurzen Satz ('reason').\n"
            "5. AUSSCHLIESSLICH DEUTSCH."
        ),
    )


def extract_framework_collaborative(
    news_text: str,
    topic: str,
    model_name: str,
) -> ArgumentationFramework:
    """
    Executes the collaborative multi-agent debate workflow:
    1. Parallel extraction: Advocatus (Pro) + Skeptiker (Contra)
    2. Deduplication & indexing (A1, A2, A3 ...)
    3. Cross-Examiner refutation round for Dung attack relations (A -> B)
    """
    pro_prompt = f"Thema: {topic}\n\nQuellenkorpus:\n{news_text}"
    contra_prompt = f"Thema: {topic}\n\nQuellenkorpus:\n{news_text}"

    # Step 1: Run Pro and Contra agents in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_pro = executor.submit(get_pro_agent(model_name).run_sync, pro_prompt)
        future_contra = executor.submit(get_contra_agent(model_name).run_sync, contra_prompt)

        pro_result = future_pro.result().output
        contra_result = future_contra.result().output

    # Step 2: Unify and re-index all arguments into clean A1, A2, A3 ...
    raw_args = list(pro_result.arguments) + list(contra_result.arguments)
    unified_arguments: list[Argument] = []
    seen_claims: set[str] = set()

    for idx, raw_arg in enumerate(raw_args, 1):
        clean_claim = raw_arg.claim.strip()
        # Basic normalization for deduplication
        norm_key = re.sub(r"\W+", " ", clean_claim.lower()).strip()
        if norm_key in seen_claims:
            continue
        seen_claims.add(norm_key)

        unified_id = f"A{len(unified_arguments) + 1}"
        unified_arguments.append(
            Argument(
                id=unified_id,
                claim=clean_claim,
                source_url=raw_arg.source_url.strip() or "KEINE_QUELLE",
            )
        )

    if not unified_arguments:
        return ArgumentationFramework(topic=topic, arguments=[], attacks=[])

    # Step 3: Adversarial Cross-Examination round
    arg_list_text = "\n".join(
        f"- {arg.id}: {arg.claim} [Quelle: {arg.source_url}]"
        for arg in unified_arguments
    )
    cross_prompt = (
        f"Thema: {topic}\n\n"
        f"Hier sind alle identifizierten Argumente:\n{arg_list_text}\n\n"
        "Identifiziere alle logischen Angriffsrelationen und wechselseitigen Dilemmata zwischen diesen Argumenten."
    )

    attacks_res = get_cross_examiner_agent(model_name).run_sync(cross_prompt).output
    known_ids = {arg.id for arg in unified_arguments}

    # Validate and filter attacks to known IDs without self-attacks
    valid_attacks: list[Attack] = []
    seen_attacks: set[tuple[str, str]] = set()

    for att in attacks_res.attacks:
        if (
            att.attacker_id in known_ids
            and att.target_id in known_ids
            and att.attacker_id != att.target_id
            and (att.attacker_id, att.target_id) not in seen_attacks
        ):
            seen_attacks.add((att.attacker_id, att.target_id))
            valid_attacks.append(
                Attack(
                    attacker_id=att.attacker_id,
                    target_id=att.target_id,
                    reason=att.reason.strip(),
                )
            )

    return ArgumentationFramework(
        topic=topic,
        arguments=unified_arguments,
        attacks=valid_attacks,
    )


@functools.lru_cache(maxsize=4)
def get_extraction_agent(model_name: str) -> Agent[None, ArgumentationFramework]:
    model = _resolve_model(model_name)

    return Agent(
        model,
        output_type=ArgumentationFramework,
        system_prompt=(
            "Du bist ein führender Experte für formale Argumentationslogik (Dung Abstract Argumentation Frameworks).\n"
            "Deine Aufgabe: Analysiere den bereitgestellten Quellenkorpus neutral und logisch präzise.\n\n"
            "Strikte Regeln:\n"
            "1. THEMENTREUE: Extrahiere AUSSCHLIESSLICH Argumente, die sich direkt und inhaltlich auf das angegebene Thema beziehen. Ignoriere themenfremde Nachrichten vollständig.\n"
            "2. HOHE ARGUMENTENDICHTE: Extrahiere möglichst viele unterscheidbare Pro- und Contra-Thesen (Ziel: 15–30 Argumente). IDs strikt als A1, A2, A3 ... vergeben.\n"
            "3. ECHTE ANGRIFFSRELATIONEN: Ein Angriff A -> B darf NUR existieren, wenn Argument A die Gültigkeit, Prämisse oder Wirksamkeit von Argument B direkt logisch widerlegt, kritisiert oder einschränkt (inklusive wechselseitiger Dilemmata A ↔ B). Niemals themenfremde Angriffe erfinden.\n"
            "4. TOKEN-EFFIZIENZ: Jede Behauptung (claim) in 1–2 klaren Sätzen formulieren. Angriffsbegründung (reason) in maximal 1 kurzen Satz fassen.\n"
            "5. QUELLENTREUE: Trage als 'source_url' die exakte URL des Quellartikels ein (oder KEINE_QUELLE). Keine erfundenen URLs.\n"
            "6. SPRACHE: AUSSCHLIESSLICH DEUTSCH. Verwende niemals chinesische oder andere fremdsprachige Zeichen."
        ),
    )


def get_synthesis_agent(model_name: str) -> Agent[None, FullAnalysisResult]:
    model = _resolve_model(model_name)

    return Agent(
        model,
        output_type=FullAnalysisResult,
        system_prompt=(
            "Du erhältst ein formales Argumentationsframework und berechnete Perspektiven (Extensions).\n"
            "Formuliere für jede Perspektive:\n"
            "- 'title': prägnanter deutscher Titel (max. 4 Wörter)\n"
            "- 'thesis': eine sachliche, prägnante Kernaussage (1–2 Sätze auf Deutsch)\n"
            "Regeln: Keine Wertung, kein Ranking. AUSSCHLIESSLICH DEUTSCH (kein Chinesisch, kein Englisch)."
        ),
    )
