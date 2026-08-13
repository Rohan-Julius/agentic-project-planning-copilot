"""Requirements endpoint tests (spec §16.6, §18) — the Planning Workspace's Requirements
section needs the full grounded record (description, citations), not just the summary
fields the read schema originally exposed.
"""
from __future__ import annotations

from app.models.requirement import RequirementRecord


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Leave Management"})
    return resp.json()["project_id"]


def _seed_requirement(client, project_id: str, **overrides) -> None:
    payload = {
        "requirement_id": "REQ-001",
        "title": "Employees can request leave",
        "description": "Employees must be able to submit a leave request with a date range.",
        "category": "functional",
        "confidence": 0.9,
        "classification": "SOURCE_BACKED",
        "source_references": [
            {"document_name": "hr-policy.pdf", "page_number": 3, "section": "Leave", "chunk_id": "doc_1-CH-001"}
        ],
        **overrides,
    }
    with client.session_factory() as session:
        session.add(
            RequirementRecord(
                requirement_id=payload["requirement_id"],
                project_id=project_id,
                title=payload["title"],
                category=payload["category"],
                classification=payload["classification"],
                confidence=payload["confidence"],
                payload_json=payload,
            )
        )
        session.commit()


def test_get_requirements_includes_description_and_citations(client):
    project_id = _create_project(client)
    _seed_requirement(client, project_id)

    resp = client.get(f"/projects/{project_id}/requirements")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    req = body[0]
    assert req["requirement_id"] == "REQ-001"
    assert req["description"] == "Employees must be able to submit a leave request with a date range."
    assert req["source_references"] == [
        {"document_name": "hr-policy.pdf", "page_number": 3, "section": "Leave", "chunk_id": "doc_1-CH-001"}
    ]


def test_get_requirements_defaults_to_empty_description_and_citations_if_payload_lacks_them(client):
    """Defensive: an older/malformed payload_json missing these keys shouldn't 500."""
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            RequirementRecord(
                requirement_id="REQ-002",
                project_id=project_id,
                title="Bare-bones requirement",
                category="functional",
                classification="ASSUMPTION",
                confidence=0.5,
                payload_json={},
            )
        )
        session.commit()

    resp = client.get(f"/projects/{project_id}/requirements")

    assert resp.status_code == 200
    req = resp.json()[0]
    assert req["description"] == ""
    assert req["source_references"] == []


def test_get_requirements_is_project_isolated(client):
    project_a = _create_project(client)
    project_b = _create_project(client)
    _seed_requirement(client, project_a)

    resp = client.get(f"/projects/{project_b}/requirements")

    assert resp.status_code == 200
    assert resp.json() == []


def test_get_requirements_empty_for_project_with_none(client):
    project_id = _create_project(client)

    resp = client.get(f"/projects/{project_id}/requirements")

    assert resp.status_code == 200
    assert resp.json() == []
