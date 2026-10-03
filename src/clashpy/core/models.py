"""Domain models. Pure Pydantic definitions without external solver/LLM coupling."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, model_validator


class Argument(BaseModel):
    id: str = Field(min_length=1, description="Unique argument identifier, e.g. A1")
    claim: str = Field(description="Concise claim or statement")
    source_url: str = Field(description="Exact source article URL or KEINE_QUELLE")


class Attack(BaseModel):
    attacker_id: str
    target_id: str
    reason: str


class ArgumentList(BaseModel):
    arguments: List[Argument]


class AttackList(BaseModel):
    attacks: List[Attack]


class ArgumentationFramework(BaseModel):
    topic: str
    arguments: List[Argument]
    attacks: List[Attack]

    @model_validator(mode="after")
    def validate_graph(self) -> "ArgumentationFramework":
        argument_ids = [argument.id for argument in self.arguments]
        if any(not argument_id.strip() for argument_id in argument_ids):
            raise ValueError("Argument IDs must not be blank")

        duplicate_ids = sorted(
            argument_id
            for argument_id in set(argument_ids)
            if argument_ids.count(argument_id) > 1
        )
        if duplicate_ids:
            raise ValueError(
                f"Argument IDs must be unique; duplicates: {', '.join(duplicate_ids)}"
            )

        known_ids = set(argument_ids)
        invalid_attacks = [
            f"{attack.attacker_id}->{attack.target_id}"
            for attack in self.attacks
            if attack.attacker_id not in known_ids or attack.target_id not in known_ids
        ]
        if invalid_attacks:
            raise ValueError(
                "Attacks must reference known argument IDs; invalid: "
                + ", ".join(invalid_attacks)
            )

        return self


class GroupThesis(BaseModel):
    group_id: int
    thesis: str
    title: str


class FullAnalysisResult(BaseModel):
    theses: List[GroupThesis]
