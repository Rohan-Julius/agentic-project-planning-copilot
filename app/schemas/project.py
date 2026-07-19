"""Project creation and read schemas (spec §16.2)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.clarification import ClarificationAnswerInfo
from app.schemas.enums import Methodology


class ProjectCreate(BaseModel):
    """Fields captured on project creation (spec §16.2).

    Methodology is fixed to Agile/Scrum by project decision (see enums.Methodology) —
    the field is still explicit (rather than omitted) so the UI/API contract is self-
    documenting and future methodologies could be added without breaking the schema.
    """

    name: str = Field(min_length=1)
    description: str = ""
    business_domain: str = ""
    methodology: Methodology = Methodology.AGILE_SCRUM
    expected_duration_weeks: int | None = Field(default=None, ge=1)
    team_composition: str = ""
    target_platforms: list[str] = Field(default_factory=list)
    technology_constraints: list[str] = Field(default_factory=list)


class ProjectRead(ProjectCreate):
    project_id: str
    status: str


class ProjectInfo(BaseModel):
    """`get_project_information` tool return shape (spec §9.3)."""

    project_id: str
    name: str
    description: str = ""
    methodology: Methodology
    expected_duration_weeks: int | None = None
    team_composition: str = ""
    target_platforms: list[str] = Field(default_factory=list)
    technology_constraints: list[str] = Field(default_factory=list)
    existing_clarification_answers: list[ClarificationAnswerInfo] = Field(default_factory=list)
