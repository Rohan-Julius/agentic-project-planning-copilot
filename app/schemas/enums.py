"""Closed vocabularies shared across schemas (spec §12.5, §13, §14)."""
from __future__ import annotations

from enum import Enum
from typing import Literal

# --- Grounding (§12.5) ---
Classification = Literal[
    "SOURCE_BACKED",
    "CLARIFICATION_BACKED",
    "ASSUMPTION",
    "AI_RECOMMENDATION",
]

# --- Requirement categories (§14 example) ---
RequirementCategory = Literal[
    "functional",
    "non_functional",
    "business_rule",
    "constraint",
    "integration",
    "data",
    "security",
]

# --- Shared priority scale (§14 UserStory example) ---
Priority = Literal["Highest", "High", "Medium", "Low"]

# --- RAID probability/impact/severity scale ---
ImpactLevel = Literal["Low", "Medium", "High"]

# --- Reviewer decision (§7.4) ---
ReviewerDecision = Literal["PASS", "PASS_WITH_WARNINGS", "REVISION_REQUIRED"]

# --- Clarification lifecycle (§11 approval point 1 actions) ---
ClarificationStatus = Literal["PENDING", "ANSWERED", "DEFERRED", "NOT_APPLICABLE"]

# --- Supervisor allowed actions (§7.1) ---
SupervisorAction = Literal[
    "RUN_REQUIREMENT_ANALYST",
    "WAIT_FOR_CLARIFICATIONS",
    "RUN_PLANNING_AGENT",
    "RUN_REVIEWER_AGENT",
    "REVISE_PLAN",
    "WAIT_FOR_FINAL_APPROVAL",
    "EXPORT_PLAN",
    "STOP_WITH_ERROR",
]

# --- Technical task categories (§13.7) ---
TechnicalTaskCategory = Literal[
    "Frontend",
    "Backend",
    "Database",
    "Integration",
    "Testing",
    "Security",
    "Deployment",
    "Monitoring",
    "Documentation",
]

# --- Dependency type (§13.8) — minimal closed set, extendable without migration ---
DependencyType = Literal["BLOCKS", "REQUIRES", "RELATES_TO"]

# --- No-evidence behaviour (§12.6) — never invent; signal explicitly instead ---
NoEvidenceSignal = Literal["CLARIFICATION_REQUIRED", "NO_SUPPORTING_SOURCE_FOUND"]


class Methodology(str, Enum):
    """Project delivery methodology.

    Restricted to Agile/Scrum only per project decision — the milestone-based planning
    path in spec §13.10 is intentionally out of scope. See docs/ARCHITECTURE.md §5b.
    """

    AGILE_SCRUM = "agile_scrum"
