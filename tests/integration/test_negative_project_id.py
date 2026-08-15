"""Cross-endpoint negative test (spec §25 'missing project ID') — every endpoint that takes
a project_id path parameter must return a clean 404 for a project that doesn't exist, never
a 500 or an unhandled crash. Each router implements this via its own `_require_project`
helper; this test sweeps all of them in one place so the invariant can't silently regress
one router at a time.
"""
from __future__ import annotations

import pytest

UNKNOWN_PROJECT_ID = "proj_does_not_exist"

GET_ENDPOINTS = [
    f"/projects/{UNKNOWN_PROJECT_ID}",
    f"/projects/{UNKNOWN_PROJECT_ID}/documents",
    f"/projects/{UNKNOWN_PROJECT_ID}/requirements",
    f"/projects/{UNKNOWN_PROJECT_ID}/clarifications",
    f"/projects/{UNKNOWN_PROJECT_ID}/plan",
    f"/projects/{UNKNOWN_PROJECT_ID}/review",
    f"/projects/{UNKNOWN_PROJECT_ID}/workflow/status",
    f"/projects/{UNKNOWN_PROJECT_ID}/workflow/events",
    f"/projects/{UNKNOWN_PROJECT_ID}/export/json",
    f"/projects/{UNKNOWN_PROJECT_ID}/export/markdown",
    f"/projects/{UNKNOWN_PROJECT_ID}/export/jira-csv",
    f"/projects/{UNKNOWN_PROJECT_ID}/export/zip",
]

POST_ENDPOINTS = [
    f"/projects/{UNKNOWN_PROJECT_ID}/index",
    f"/projects/{UNKNOWN_PROJECT_ID}/workflow/start",
    f"/projects/{UNKNOWN_PROJECT_ID}/workflow/abandon",
    f"/projects/{UNKNOWN_PROJECT_ID}/clarifications/answers",
    f"/projects/{UNKNOWN_PROJECT_ID}/clarifications/approve",
    f"/projects/{UNKNOWN_PROJECT_ID}/plan/approve",
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_endpoint_returns_404_for_unknown_project(client, path):
    response = client.get(path)
    assert response.status_code == 404, f"{path} returned {response.status_code}, not 404"
    assert UNKNOWN_PROJECT_ID in response.json()["detail"]


@pytest.mark.parametrize("path", POST_ENDPOINTS)
def test_post_endpoint_returns_404_for_unknown_project(client, path):
    response = client.post(path, json=[] if "answers" in path else None)
    assert response.status_code == 404, f"{path} returned {response.status_code}, not 404"
    assert UNKNOWN_PROJECT_ID in response.json()["detail"]


def test_document_upload_returns_404_for_unknown_project(client):
    response = client.post(
        f"/projects/{UNKNOWN_PROJECT_ID}/documents",
        files={"file": ("requirements.txt", b"some content", "text/plain")},
    )
    assert response.status_code == 404
    assert UNKNOWN_PROJECT_ID in response.json()["detail"]
