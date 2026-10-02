import pytest

from clashpy.adapters.classifiers.dense_filter import (
    _is_boilerplate,
    prune_article_text,
    prune_corpus,
    score_sentence_argument_density,
)
from clashpy.llm.agents import _resolve_model


def test_score_sentence_argument_density():
    # High density sentence with argument marker and topic
    high_sent = "Die 4-Tage-Woche senkt Burnout signifikant, jedoch warnen Kritiker vor Fachkräftemangel."
    score_high = score_sentence_argument_density(high_sent, topic="4-Tage-Woche")

    # Fluff sentence without argument value
    fluff_sent = "Der Bundeskanzler reiste gestern nach Paris zu Gesprächen."
    score_fluff = score_sentence_argument_density(fluff_sent, topic="4-Tage-Woche")

    assert score_high > score_fluff
    assert score_high >= 5.0


def test_boilerplate_detection():
    assert _is_boilerplate("Akzeptieren Sie unsere Cookies und Datenschutzbestimmungen.") is True
    assert _is_boilerplate("Abonnieren Sie unseren täglichen Newsletter.") is True
    assert _is_boilerplate("Studien belegen eine Produktivitätssteigerung um 20%.") is False


def test_prune_article_text():
    article = """Title: Debatte über Arbeitszeit
Content: Willkommen zu unserem Live-Ticker. Cookie Einstellungen anpassen. Eine neue Pilotstudie belegt, dass 4-Tage-Wochen den Krankenstand um 30% reduzieren. Jedoch warnen Wirtschaftsverbände vor akuten Produktionsausfällen im Mittelstand. Folgen Sie uns auf Instagram.
Source: https://example.com/news/1"""

    pruned = prune_article_text(article, topic="Arbeitszeit", max_sentences_per_article=2)

    assert "Title: Debatte über Arbeitszeit" in pruned
    assert "Pilotstudie belegt" in pruned
    assert "warnen Wirtschaftsverbände" in pruned
    assert "Cookie" not in pruned
    assert "Instagram" not in pruned
    assert "Source: https://example.com/news/1" in pruned


def test_prune_corpus():
    corpus = """Title: News A
Content: Forscher belegen Effizienzgewinne durch KI.
Source: https://a.com

Title: News B
Content: Allerdings bestehen erhebliche KI Sicherheitsrisiken.
Source: https://b.com

Title: Unrelated News C
Content: SpaceX hat drei Raketen erfolgreich gestartet.
Source: https://c.com"""

    pruned = prune_corpus(corpus, topic="KI")
    assert "News A" in pruned
    assert "News B" in pruned
    # Unrelated news should be completely pruned away
    assert "Unrelated News C" not in pruned
    assert "SpaceX" not in pruned


def test_resolve_local_m4_models():
    # Ollama alias
    model_ollama = _resolve_model("ollama:qwen2.5:7b")
    assert hasattr(model_ollama, "model_name")
    assert model_ollama.model_name == "qwen2.5:7b"

    # Local / M4 shortcut
    model_m4 = _resolve_model("m4")
    assert hasattr(model_m4, "model_name")
