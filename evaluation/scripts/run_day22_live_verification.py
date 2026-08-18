"""Day 22 live verification: one full pipeline run against scenario 1 (leave management,
the fastest scenario per Days 15/19's timing data), confirming Tasks 1 and 3's fixes actually
change live-model output — not just that their prompts/code changed. Reuses
run_repeatability_evaluation's gate-loop driving pattern rather than reimplementing it.
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.scripts.run_extraction_evaluation import compute_agent_durations
from evaluation.scripts.run_repeatability_evaluation import _latest_recommend_action

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[2] / "sample_documents"
SCENARIO_PATH = DATASETS_DIR / "scenario_1_leave_management" / "requirements.md"

# Same 5 organizational standards Day 21 uses (evaluation/scripts/run_retrieval_evaluation.py)
# — the first attempt at this script omitted this step entirely, leaving the Planning Agent
# with zero company-standards context for the whole run (not just the estimation scale),
# which is the confirmed root cause of that run's stories_with_story_points: "0/18".
STANDARDS = [
    ("definition_of_ready.md", "Definition of Ready"),
    ("definition_of_done.md", "Definition of Done"),
    ("user_story_template.md", "User story"),
    ("security_checklist.md", "Security"),
    ("estimation_guidance.md", "Estimation"),
]


def _seed_organizational_standards(client) -> None:
    for filename, category in STANDARDS:
        with (SAMPLE_DOCS_DIR / filename).open("rb") as f:
            resp = client.post(
                "/organizational-documents",
                files={"file": (filename, f, "text/markdown")},
                data={"document_type": category},
            )
        assert resp.status_code == 201, resp.text
    index_resp = client.post("/organizational-documents/index")
    assert index_resp.status_code == 200, index_resp.text


def run(client) -> dict:
    _seed_organizational_standards(client)

    create_resp = client.post(
        "/projects", json={"name": "Day22 Live Verification", "methodology": "agile_scrum"},
    )
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["project_id"]

    with SCENARIO_PATH.open("rb") as f:
        upload_resp = client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.md", f, "text/markdown")},
            data={"document_type": "business_requirement"},
        )
    assert upload_resp.status_code == 201, upload_resp.text
    assert client.post(f"/projects/{project_id}/index").status_code == 200
    assert client.post(f"/projects/{project_id}/workflow/start").status_code == 200

    status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
    attempts = 0
    while status == "WAITING_FOR_HUMAN_INPUT" and attempts < 6:
        action = _latest_recommend_action(client, project_id)
        endpoint = (
            "plan/approve" if action == "RECOMMEND_WAIT_FOR_FINAL_APPROVAL"
            else "clarifications/approve"
        )
        approve_resp = client.post(f"/projects/{project_id}/{endpoint}")
        assert approve_resp.status_code == 200, approve_resp.text
        status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
        attempts += 1

    plan_resp = client.get(f"/projects/{project_id}/plan")
    plan = plan_resp.json() if plan_resp.status_code == 200 else None
    requirements = client.get(f"/projects/{project_id}/requirements").json()

    from app.tools.validation_tools import check_traceability, validate_project_plan

    session_factory = client.session_factory
    validation = validate_project_plan(project_id, session_factory=session_factory)
    traceability = check_traceability(project_id, session_factory=session_factory)
    total = len(traceability.matrix.rows) or 1
    coverage_pct = round((total - len(traceability.coverage_gaps)) / total * 100, 1)

    # Citation-field accuracy: for every SOURCE_BACKED requirement, does its recorded
    # section match the real document_chunk_meta.section for that chunk_id? (Task 1 proof.)
    from app.models.document import DocumentChunkMeta

    session = session_factory()
    try:
        real_sections = {
            row.chunk_id: row.section
            for row in session.query(DocumentChunkMeta).filter_by(project_id=project_id).all()
        }
    finally:
        session.close()
    section_matches, section_checked = 0, 0
    for req in requirements:
        for ref in req.get("source_references", []):
            if ref["chunk_id"] in real_sections:
                section_checked += 1
                if ref["section"] == real_sections[ref["chunk_id"]]:
                    section_matches += 1

    # Story points (Task 3 proof.)
    stories = plan["stories"] if plan else []
    stories_with_points = sum(1 for s in stories if s.get("suggested_story_points") is not None)

    events = client.get(f"/projects/{project_id}/workflow/events").json()

    return {
        "project_id": project_id,
        "final_status": status,
        "requirement_count": len(requirements),
        "epic_count": len(plan["epics"]) if plan else None,
        "story_count": len(stories),
        "traceability_coverage_pct": coverage_pct,
        "coverage_gap_count": len(traceability.coverage_gaps),
        "validation_is_valid": validation.is_valid,
        "validation_error_count": len(validation.errors),
        "citation_section_accuracy": (
            f"{section_matches}/{section_checked}" if section_checked else "n/a"
        ),
        "stories_with_story_points": f"{stories_with_points}/{len(stories)}" if stories else "n/a",
        "agent_durations": compute_agent_durations(events),
        "duration_ms_populated": any(e.get("duration_ms") for e in events),
    }


def write_report(result: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "day22_live_verification.md").write_text(
        "# Day 22 Live Verification (scenario 1)\n\n"
        f"```\n{json.dumps(result, indent=2, default=str)}\n```\n"
    )


def main(client) -> dict:
    result = run(client)
    write_report(result)
    return result
