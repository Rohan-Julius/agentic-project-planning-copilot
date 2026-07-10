"""Day 3: project CRUD API tests (spec §18)."""
from __future__ import annotations


def test_create_and_get_project(client):
    response = client.post(
        "/projects",
        json={"name": "Leave Management", "description": "HR leave system"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Leave Management"
    assert body["methodology"] == "agile_scrum"
    assert body["status"] == "CREATED"
    project_id = body["project_id"]

    get_response = client.get(f"/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["project_id"] == project_id


def test_list_projects(client):
    client.post("/projects", json={"name": "A"})
    client.post("/projects", json={"name": "B"})
    response = client.get("/projects")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_missing_project_returns_404(client):
    response = client.get("/projects/does-not-exist")
    assert response.status_code == 404


def test_create_project_requires_name(client):
    response = client.post("/projects", json={"name": ""})
    assert response.status_code == 422
