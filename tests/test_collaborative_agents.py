from unittest.mock import MagicMock, patch

import pytest

from clashpy.core.models import (
    Argument,
    ArgumentationFramework,
    ArgumentList,
    Attack,
    AttackList,
)
from clashpy.llm.agents import (
    extract_framework_collaborative,
    get_contra_agent,
    get_cross_examiner_agent,
    get_pro_agent,
)


def test_agent_factories_initialization():
    pro_agent = get_pro_agent("test")
    contra_agent = get_contra_agent("test")
    cross_agent = get_cross_examiner_agent("test")

    assert pro_agent is not None
    assert contra_agent is not None
    assert cross_agent is not None


def test_extract_framework_collaborative_workflow():
    pro_data = ArgumentList(
        arguments=[
            Argument(id="P1", claim="4-Tage-Woche senkt Burnout.", source_url="http://news.com/pro1"),
            Argument(id="P2", claim="Krankheitsausfälle sinken um 30%.", source_url="http://news.com/pro2"),
        ]
    )
    contra_data = ArgumentList(
        arguments=[
            Argument(id="C1", claim="Fachkräftemangel verhindert Verdichtung.", source_url="http://news.com/contra1"),
            Argument(id="C2", claim="Hohe Kosten für Schichtbetriebe.", source_url="http://news.com/contra2"),
        ]
    )
    cross_data = AttackList(
        attacks=[
            Attack(attacker_id="A3", target_id="A1", reason="Fachkräftemangel macht Verdichtung unmöglich."),
            Attack(attacker_id="A1", target_id="A3", reason="Geringerer Krankenstand kompensiert Fachkräftemangel."),
        ]
    )

    mock_pro = MagicMock()
    mock_pro.run_sync.return_value = MagicMock(output=pro_data)

    mock_contra = MagicMock()
    mock_contra.run_sync.return_value = MagicMock(output=contra_data)

    mock_cross = MagicMock()
    mock_cross.run_sync.return_value = MagicMock(output=cross_data)

    with (
        patch("clashpy.llm.agents.get_pro_agent", return_value=mock_pro),
        patch("clashpy.llm.agents.get_contra_agent", return_value=mock_contra),
        patch("clashpy.llm.agents.get_cross_examiner_agent", return_value=mock_cross),
    ):
        af = extract_framework_collaborative(
            news_text="Sample news",
            topic="4-Tage-Woche",
            model_name="google:gemini-3.5-flash",
        )

    assert af.topic == "4-Tage-Woche"
    assert len(af.arguments) == 4
    assert [a.id for a in af.arguments] == ["A1", "A2", "A3", "A4"]
    assert len(af.attacks) == 2
    assert af.attacks[0].attacker_id == "A3"
    assert af.attacks[0].target_id == "A1"
    assert af.attacks[1].attacker_id == "A1"
    assert af.attacks[1].target_id == "A3"
