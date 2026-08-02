"""Export builder tests (Day 14, spec §9.11, §13, §17, §20.2, §20.5) — pure functions,
no DB, no filesystem beyond the write_* tests' tmp_path.
"""
from __future__ import annotations

import csv
import io
import zipfile

from app.schemas.common import SourceReference
from app.schemas.planning import (
    AcceptanceCriterion,
    Epic,
    ProjectPlan,
    ProjectSummary,
    Scope,
    UserStory,
)
from app.schemas.reviewer import ReviewerReport
from app.services.export_service import (
    JIRA_CSV_COLUMNS,
    approval_label,
    build_jira_csv_rows,
    build_jira_csv_text,
    build_json_export,
    build_markdown_export,
    build_zip_bytes,
    format_source_references,
    write_jira_csv_file,
    write_json_file,
    write_markdown_file,
    write_reviewer_report_file,
)


def _sample_plan() -> ProjectPlan:
    ref = SourceReference(
        document_name="requirements.pdf", page_number=2, section="Leave", chunk_id="DOC-1-CH-001"
    )
    return ProjectPlan(
        summary=ProjectSummary(
            business_problem="Manual leave tracking is slow.",
            proposed_solution="Build a leave management system.",
        ),
        scope=Scope(in_scope=["Leave requests"], out_of_scope=["Payroll integration"]),
        epics=[
            Epic(
                epic_id="EPIC-001", title="Leave requests", objective="Let employees request leave",
                business_value="Reduces manual tracking", priority="High",
                classification="SOURCE_BACKED", source_references=[ref],
            )
        ],
        stories=[
            UserStory(
                story_id="US-001", epic_id="EPIC-001", title="Submit leave request",
                persona="Employee", story_statement="request leave", business_value="track time off",
                priority="High", classification="SOURCE_BACKED", source_references=[ref],
                acceptance_criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC-001", given="an employee is logged in",
                        when="they submit a leave request", then="the request is recorded",
                    )
                ],
                suggested_story_points=3, confidence=0.8,
            )
        ],
    )


def test_approval_label_reflects_final_approved_flag():
    assert approval_label(True) == "APPROVED"
    assert approval_label(False) == "DRAFT_PENDING_APPROVAL"


def test_build_json_export_never_labels_unapproved_plan_as_approved():
    plan = _sample_plan()
    unapproved = build_json_export(plan, approved=False)
    approved = build_json_export(plan, approved=True)

    assert unapproved["export_metadata"]["approval_status"] == "DRAFT_PENDING_APPROVAL"
    assert approved["export_metadata"]["approval_status"] == "APPROVED"
    assert unapproved["plan"]["epics"][0]["epic_id"] == "EPIC-001"


def test_build_jira_csv_rows_matches_spec_17_mapping():
    rows = build_jira_csv_rows(_sample_plan())

    assert len(rows) == 2
    epic_row, story_row = rows
    assert set(epic_row.keys()) == set(JIRA_CSV_COLUMNS)
    assert epic_row["Issue Type"] == "Epic"
    assert epic_row["Summary"] == "Leave requests"
    assert epic_row["AI Classification"] == "SOURCE_BACKED"
    assert story_row["Issue Type"] == "Story"
    assert story_row["Epic Link"] == "EPIC-001"
    assert story_row["Story Points"] == "3"
    assert "Given an employee is logged in" in story_row["Acceptance Criteria"]
    assert "requirements.pdf p.2" in story_row["Source References"]


def test_build_jira_csv_text_is_valid_csv_with_header():
    text = build_jira_csv_text(_sample_plan())
    reader = csv.DictReader(io.StringIO(text))

    assert reader.fieldnames == JIRA_CSV_COLUMNS
    rows = list(reader)
    assert len(rows) == 2


def test_build_markdown_export_includes_all_artifact_families_and_status():
    plan = _sample_plan()
    markdown = build_markdown_export(plan, approved=False)

    assert "DRAFT_PENDING_APPROVAL" in markdown
    assert "EPIC-001: Leave requests" in markdown
    assert "US-001: Submit leave request (Epic: EPIC-001)" in markdown
    assert "AC-001: Given an employee is logged in" in markdown
    assert "## 8. Traceability Matrix" in markdown


def test_write_json_file_never_writes_into_the_documents_directory(tmp_path):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    export_dir = tmp_path / "exports"

    path = write_json_file("proj_1", _sample_plan(), approved=True, export_dir=export_dir)

    assert path.exists()
    assert path.is_relative_to(export_dir)
    assert not path.is_relative_to(documents_dir)
    assert list(documents_dir.iterdir()) == []


def test_write_markdown_and_jira_csv_files_are_created(tmp_path):
    export_dir = tmp_path / "exports"
    plan = _sample_plan()

    md_path = write_markdown_file("proj_1", plan, approved=True, export_dir=export_dir)
    csv_path = write_jira_csv_file("proj_1", plan, export_dir=export_dir)

    assert md_path.read_text().startswith("# Project Plan")
    assert "Issue Type" in csv_path.read_text()


def test_write_reviewer_report_file(tmp_path):
    export_dir = tmp_path / "exports"
    report = ReviewerReport(decision="PASS_WITH_WARNINGS", warnings=["Story US-001 could be split."])

    path = write_reviewer_report_file("proj_1", report, export_dir=export_dir)

    assert '"decision": "PASS_WITH_WARNINGS"' in path.read_text()


def test_build_zip_bytes_contains_every_written_file(tmp_path):
    export_dir = tmp_path / "exports"
    plan = _sample_plan()
    paths = {
        "json": write_json_file("proj_1", plan, approved=True, export_dir=export_dir),
        "markdown": write_markdown_file("proj_1", plan, approved=True, export_dir=export_dir),
        "jira_csv": write_jira_csv_file("proj_1", plan, export_dir=export_dir),
    }

    zip_bytes = build_zip_bytes(paths)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())

    assert names == {"plan.json", "plan.md", "jira.csv"}


def test_format_source_references_omits_missing_page_number():
    ref = SourceReference(document_name="requirements.pdf", section="Payments", chunk_id="CH-001")
    assert format_source_references([ref]) == "requirements.pdf §Payments [CH-001]"


def test_format_source_references_omits_missing_section():
    ref = SourceReference(document_name="requirements.pdf", page_number=2, chunk_id="CH-001")
    assert format_source_references([ref]) == "requirements.pdf p.2 [CH-001]"


def test_format_source_references_bare_chunk_id_when_page_and_section_missing():
    ref = SourceReference(document_name="requirements.pdf", chunk_id="CH-001")
    assert format_source_references([ref]) == "requirements.pdf [CH-001]"


def test_format_source_references_joins_multiple_refs_with_semicolon():
    refs = [
        SourceReference(document_name="a.pdf", page_number=1, chunk_id="CH-001"),
        SourceReference(document_name="b.pdf", page_number=2, chunk_id="CH-002"),
    ]
    assert format_source_references(refs) == "a.pdf p.1 [CH-001]; b.pdf p.2 [CH-002]"


def test_format_source_references_empty_list_returns_empty_string():
    assert format_source_references([]) == ""


def test_format_source_references_preserves_unicode_document_name():
    ref = SourceReference(document_name="Café Menu.pdf", page_number=1, chunk_id="CH-001")
    assert format_source_references([ref]) == "Café Menu.pdf p.1 [CH-001]"


def test_jira_csv_rows_empty_plan_produces_no_rows():
    """A plan with zero epics and zero stories must still produce valid (empty) CSV
    structure, not an error."""
    empty_plan = ProjectPlan(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
    )

    rows = build_jira_csv_rows(empty_plan)

    assert rows == []


def test_jira_csv_text_quotes_fields_containing_commas_and_newlines():
    """CSV values containing the delimiter or embedded newlines must round-trip correctly
    through Python's csv module (proper quoting), not corrupt the row structure."""
    plan = ProjectPlan(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[
            Epic(
                epic_id="EPIC-001", title="Epic, with a comma",
                objective="Line one.\nLine two, with a comma.",
                business_value="v", priority="High", classification="ASSUMPTION",
            )
        ],
    )

    text = build_jira_csv_text(plan)
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["Summary"] == "Epic, with a comma"
    assert rows[0]["Description"] == "Line one.\nLine two, with a comma."
