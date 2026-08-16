"""Tests for Supervisor Agent (DESIGN.md §8.1, spec §7.1)."""
import pytest
from unittest.mock import Mock, patch
from app.agents.supervisor import run_supervisor_agent
from app.workflow.state import ProjectWorkflowState
from app.schemas.agents import SupervisorDecision


def _base_state() -> ProjectWorkflowState:
    """Minimal valid state for testing."""
    return {
        "project_id": "proj1",
        "current_stage": "supervisor",
        "next_action": None,
        "document_ids": ["doc1"],
        "requirement_ids": [],
        "unresolved_question_ids": [],
        "requirement_analysis_attempts": 0,
        "clarification_approved": False,
        "plan_version_id": None,
        "reviewer_decision": None,
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }


def test_supervisor_recommends_requirement_analyst_on_empty_state():
    """When no requirements exist, Supervisor recommends running analyst."""
    state = _base_state()
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="RUN_REQUIREMENT_ANALYST",
            reason="No requirements extracted yet",
            required_inputs=["documents"],
        )

        decision = run_supervisor_agent(state, mock_session)

    assert decision.next_action == "RUN_REQUIREMENT_ANALYST"


@pytest.mark.parametrize(
    "state_override,expected_action,scenario",
    [
        # Scenario 1: Empty project → analyze requirements
        ({}, "RUN_REQUIREMENT_ANALYST", "no_requirements"),
        # Scenario 2: Requirements done, clarifications pending, not approved
        (
            {
                "requirement_ids": ["req1"],
                "unresolved_question_ids": ["q1"],
                "clarification_approved": False,
            },
            "WAIT_FOR_CLARIFICATIONS",
            "clarifications_pending",
        ),
        # Scenario 3: Requirements done, no clarifications, not approved yet
        (
            {
                "requirement_ids": ["req1"],
                "unresolved_question_ids": [],
                "clarification_approved": False,
            },
            "WAIT_FOR_CLARIFICATIONS",
            "clarifications_none_but_unapproved",
        ),
        # Scenario 4: Approved but no plan yet
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": None,
            },
            "RUN_PLANNING_AGENT",
            "ready_for_planning",
        ),
        # Scenario 5: Plan done but not reviewed
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": "v1",
                "reviewer_decision": None,
            },
            "RUN_REVIEWER_AGENT",
            "ready_for_review",
        ),
        # Scenario 6: Reviewer says revision needed, revision_count < 1
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": "v1",
                "reviewer_decision": "REVISION_REQUIRED",
                "revision_count": 0,
            },
            "REVISE_PLAN",
            "revision_available",
        ),
        # Scenario 7: Reviewer says revision needed, but revision_count >= 1 (limit reached)
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": "v1",
                "reviewer_decision": "REVISION_REQUIRED",
                "revision_count": 1,
            },
            "WAIT_FOR_FINAL_APPROVAL",
            "revision_limit_reached",
        ),
        # Scenario 8: Reviewer passed, waiting for human approval
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": "v1",
                "reviewer_decision": "PASS",
                "final_approved": False,
            },
            "WAIT_FOR_FINAL_APPROVAL",
            "reviewer_pass",
        ),
        # Scenario 9: Final approval given → export
        (
            {
                "requirement_ids": ["req1"],
                "clarification_approved": True,
                "plan_version_id": "v1",
                "reviewer_decision": "PASS",
                "final_approved": True,
            },
            "EXPORT_PLAN",
            "final_approved",
        ),
        # Scenario 10: Error recorded → stop
        (
            {"errors": ["Something went wrong"]},
            "STOP_WITH_ERROR",
            "error_recorded",
        ),
    ],
)
def test_supervisor_all_scenarios(state_override, expected_action, scenario):
    """Test Supervisor decision-making across ≥8 routing scenarios."""
    state = _base_state()
    state.update(state_override)
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action=expected_action,
            reason=f"Test scenario: {scenario}",
            required_inputs=[],
        )

        decision = run_supervisor_agent(state, mock_session)

    assert decision.next_action == expected_action, f"Scenario {scenario} failed"


def test_supervisor_state_summary():
    """Test that state summary is generated and passed to prompt."""
    state = _base_state()
    state.update({"requirement_ids": ["req1", "req2"]})
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="WAIT_FOR_CLARIFICATIONS",
            reason="Test",
            required_inputs=[],
        )

        run_supervisor_agent(state, mock_session)

    # Verify that run_agent was called with a prompt containing state summary
    call_args = mock_agent.call_args
    prompt = call_args.kwargs["prompt"]
    assert "requirement" in prompt.lower()


def test_state_summary_explicitly_flags_pending_final_approval():
    """Regression test for the Day 19 evaluation finding (evaluation/reports/
    day19_evaluation_report.md §24.3): when the reviewer has passed but a human hasn't
    approved yet, the prompt must say so explicitly — mirroring the existing clarification-
    approval cue — or the model has no textual signal that WAIT_FOR_FINAL_APPROVAL (not
    EXPORT_PLAN) is correct.
    """
    state = _base_state()
    state.update({
        "requirement_ids": ["req1"],
        "clarification_approved": True,
        "plan_version_id": "v1",
        "reviewer_decision": "PASS",
        "final_approved": False,
    })
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="WAIT_FOR_FINAL_APPROVAL", reason="Test", required_inputs=[],
        )
        run_supervisor_agent(state, mock_session)

    prompt = mock_agent.call_args.kwargs["prompt"]
    assert "AWAITING human approval" in prompt
    assert "not EXPORT_PLAN" in prompt


def test_state_summary_does_not_flag_pending_final_approval_when_already_approved():
    """The new line must not fire once final_approved is True — must not contradict the
    existing "✓ Final approval: APPROVED" line right below it.
    """
    state = _base_state()
    state.update({
        "requirement_ids": ["req1"],
        "clarification_approved": True,
        "plan_version_id": "v1",
        "reviewer_decision": "PASS",
        "final_approved": True,
    })
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="EXPORT_PLAN", reason="Test", required_inputs=[],
        )
        run_supervisor_agent(state, mock_session)

    prompt = mock_agent.call_args.kwargs["prompt"]
    assert "AWAITING human approval to proceed — review passing" not in prompt
    assert "APPROVED — ready to export" in prompt


def test_supervisor_with_multiple_errors():
    """Supervisor sees multiple errors and recommends stop."""
    state = _base_state()
    state.update({
        "errors": [
            "Requirement Analyst failed to parse documents",
            "Qdrant connection timeout",
        ]
    })
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="STOP_WITH_ERROR",
            reason="Multiple errors recorded; cannot proceed",
            required_inputs=["human_intervention"],
        )

        decision = run_supervisor_agent(state, mock_session)

    assert decision.next_action == "STOP_WITH_ERROR"


def test_supervisor_passes_with_warnings_like_pass():
    """Supervisor handles PASS_WITH_WARNINGS the same as PASS."""
    state = _base_state()
    state.update({
        "requirement_ids": ["req1"],
        "clarification_approved": True,
        "plan_version_id": "v1",
        "reviewer_decision": "PASS_WITH_WARNINGS",
        "final_approved": False,
    })
    mock_session = Mock()

    with patch("app.agents.supervisor.run_agent") as mock_agent:
        mock_agent.return_value = SupervisorDecision(
            next_action="WAIT_FOR_FINAL_APPROVAL",
            reason="Plan passed review (with warnings)",
            required_inputs=["final_approval"],
        )

        decision = run_supervisor_agent(state, mock_session)

    assert decision.next_action == "WAIT_FOR_FINAL_APPROVAL"
