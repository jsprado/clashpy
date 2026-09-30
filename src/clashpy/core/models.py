"""Domain models. Pure Pydantic definitions without external solver/LLM coupling."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Argument(BaseModel):
    id: str = Field(description="Unique argument identifier, e.g. A1")
    claim: str = Field(description="Concise claim or statement")
    source_url: str = Field(description="Exact source article URL or KEINE_QUELLE")


class Attack(BaseModel):
    attacker_id: str
    target_id: str
    reason: str


class ArgumentationFramework(BaseModel):
    topic: str
    arguments: List[Argument]
    attacks: List[Attack]


class GroupThesis(BaseModel):
    group_id: int
    thesis: str
    title: str


class FullAnalysisResult(BaseModel):
    theses: List[GroupThesis]
