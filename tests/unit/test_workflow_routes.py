"""Deterministic router tests (Day 7, DESIGN.md §7.3, spec §24.3 style: table-driven
routing over >=8 situations).
"""
from __future__ import annotations

import pytest

from app.workflow.routes import (
    NODE_CLARIFICATION_GATE,
    NODE_EXPORT,
    NODE_FINAL_GATE,
    NODE_PLAN_REVISION,
    NODE_PLANNING,
    NODE_REQUIREMENT_ANALYST,
    NODE_REVIEWER,
    NODE_STOP_ERROR,
    route_next_node,
)
from app.workflow.state import ProjectWorkflowState


def _state(**overrides) -> ProjectWorkflowState:
    base: ProjectWorkflowState = {
        "project_id": "proj_x",
        "current_stage": "",
        "next_action": None,
        "document_ids": [],
        "requirement_ids": [],
        "unresolved_question_ids": [],
        "clarification_approved": False,
        "plan_version_id": None,
        "reviewer_decision": None,
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "name,state,expected",
    [
        (
            "errors present -> stop_error (unconditional, even mid-flow)",
            _state(requirement_ids=["REQ-1"], errors=["boom"]),
            NODE_STOP_ERROR,
        ),
        (
            "no documents/requirements yet -> requirement_analyst",
            _state(),
            NODE_REQUIREMENT_ANALYST,
        ),
        (
            "requirements present, unresolved questions, not approved -> clarification_gate",
            _state(requirement_ids=["REQ-1"], unresolved_question_ids=["CQ-1"]),
            NODE_CLARIFICATION_GATE,
        ),
        (
            "requirements present, zero questions, not approved -> clarification_gate (decision 2)",
            _state(requirement_ids=["REQ-1"], unresolved_question_ids=[]),
            NODE_CLARIFICATION_GATE,
        ),
        (
            "clarification approved, no plan yet -> planning",
            _state(requirement_ids=["REQ-1"], clarification_approved=True),
            NODE_PLANNING,
        ),
        (
            "plan exists, no reviewer decision yet -> reviewer",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
            ),
            NODE_REVIEWER,
        ),
        (
            "revision required, under limit -> plan_revision",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
                reviewer_decision="REVISION_REQUIRED", revision_count=0,
            ),
            NODE_PLAN_REVISION,
        ),
        (
            "revision required, limit reached -> final_gate (loop-limit, §20.1)",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
                reviewer_decision="REVISION_REQUIRED", revision_count=1,
            ),
            NODE_FINAL_GATE,
        ),
        (
            "reviewer PASS -> final_gate",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
                reviewer_decision="PASS",
            ),
            NODE_FINAL_GATE,
        ),
        (
            "reviewer PASS_WITH_WARNINGS -> final_gate",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
                reviewer_decision="PASS_WITH_WARNINGS",
            ),
            NODE_FINAL_GATE,
        ),
        (
            "final_approved wins over a stale PASS reviewer_decision (decision 3) -> export",
            _state(
                requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="ver_1",
                reviewer_decision="PASS", final_approved=True,
            ),
            NODE_EXPORT,
        ),
    ],
)
def test_route_next_node(name, state, expected):
    assert route_next_node(state) == expected, name
