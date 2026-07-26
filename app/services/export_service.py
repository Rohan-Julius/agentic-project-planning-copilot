"""Deterministic export builders (spec §9.11, §13, §16.8, §17, §20.2, §20.5).

Pure functions — no LLM, no agent involvement (§8). `write_*` functions are the only ones
that touch the filesystem, and they always write under `export_dir / project_id /`, a
directory that is never `settings.documents_dir` (source documents are never overwritten,
§20.2). Every JSON/Markdown export carries an honest `approval_status` computed from the
caller-supplied `approved` flag — nothing here ever hardcodes "approved" (§20.5).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

from app.schemas.common import SourceReference
from app.schemas.planning import ProjectPlan
from app.schemas.reviewer import ReviewerReport

JIRA_CSV_COLUMNS = [
    "Issue Type", "Summary", "Description", "Epic Name", "Epic Link", "Parent ID",
    "Priority", "Story Points", "Acceptance Criteria", "Dependencies", "Labels",
    "Source References", "AI Classification",
]


def approval_label(approved: bool) -> str:
    return "APPROVED" if approved else "DRAFT_PENDING_APPROVAL"


def format_source_references(refs: list[SourceReference]) -> str:
    parts = []
    for ref in refs:
        piece = ref.document_name
        if ref.page_number is not None:
            piece += f" p.{ref.page_number}"
        if ref.section:
            piece += f" §{ref.section}"
        piece += f" [{ref.chunk_id}]"
        parts.append(piece)
    return "; ".join(parts)


def build_json_export(
    plan: ProjectPlan, *, approved: bool, exported_at: dt.datetime | None = None
) -> dict:
    exported_at = exported_at or dt.datetime.now(dt.timezone.utc)
    return {
        "export_metadata": {
            "approval_status": approval_label(approved),
            "exported_at": exported_at.isoformat(),
        },
        "plan": plan.model_dump(mode="json"),
    }


def build_jira_csv_rows(plan: ProjectPlan) -> list[dict[str, str]]:
    """One row per Epic, one row per Story — the §17 mapping documented in
    docs/DESIGN.md §13.
    """
    rows: list[dict[str, str]] = []
    for epic in plan.epics:
        rows.append({
            "Issue Type": "Epic",
            "Summary": epic.title,
            "Description": epic.description or epic.objective,
            "Epic Name": epic.title,
            "Epic Link": "",
            "Parent ID": "",
            "Priority": epic.priority,
            "Story Points": "",
            "Acceptance Criteria": "",
            "Dependencies": ", ".join(epic.dependencies),
            "Labels": epic.classification,
            "Source References": format_source_references(epic.source_references),
            "AI Classification": epic.classification,
        })
    for story in plan.stories:
        ac_text = " | ".join(
            f"Given {ac.given} When {ac.when} Then {ac.then}" for ac in story.acceptance_criteria
        )
        rows.append({
            "Issue Type": "Story",
            "Summary": story.title,
            "Description": story.story_statement,
            "Epic Name": "",
            "Epic Link": story.epic_id,
            "Parent ID": story.epic_id,
            "Priority": story.priority,
            "Story Points": "" if story.suggested_story_points is None else str(story.suggested_story_points),
            "Acceptance Criteria": ac_text,
            "Dependencies": ", ".join(story.dependencies),
            "Labels": story.classification,
            "Source References": format_source_references(story.source_references),
            "AI Classification": story.classification,
        })
    return rows


def build_jira_csv_text(plan: ProjectPlan) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=JIRA_CSV_COLUMNS)
    writer.writeheader()
    for row in build_jira_csv_rows(plan):
        writer.writerow(row)
    return buf.getvalue()


def build_markdown_export(
    plan: ProjectPlan, *, approved: bool, exported_at: dt.datetime | None = None
) -> str:
    exported_at = exported_at or dt.datetime.now(dt.timezone.utc)
    lines: list[str] = [
        "# Project Plan (AI-Generated Draft)",
        "",
        f"**Status:** {approval_label(approved)}",
        f"**Exported:** {exported_at.isoformat()}",
        "",
        "## 1. Project Summary",
        f"- **Business problem:** {plan.summary.business_problem}",
        f"- **Proposed solution:** {plan.summary.proposed_solution}",
    ]
    for label, values in (
        ("Objectives", plan.summary.objectives),
        ("Target users", plan.summary.target_users),
        ("Expected benefits", plan.summary.expected_benefits),
        ("Success criteria", plan.summary.success_criteria),
        ("Major constraints", plan.summary.major_constraints),
    ):
        if values:
            lines.append(f"- **{label}:** " + "; ".join(values))

    lines += ["", "## 2. Scope"]
    for label, values in (
        ("In scope", plan.scope.in_scope),
        ("Out of scope", plan.scope.out_of_scope),
        ("Future scope", plan.scope.future_scope),
        ("Assumptions", plan.scope.assumptions),
        ("Constraints", plan.scope.constraints),
    ):
        lines.append(f"### {label}")
        if values:
            lines.extend(f"- {v}" for v in values)
        else:
            lines.append("- (none)")

    lines += ["", "## 3. Epics"]
    if not plan.epics:
        lines.append("(none)")
    for epic in plan.epics:
        lines.append(f"### {epic.epic_id}: {epic.title} `[{epic.classification}]`")
        lines.append(f"- **Objective:** {epic.objective}")
        lines.append(f"- **Business value:** {epic.business_value}")
        lines.append(f"- **Priority:** {epic.priority}")
        if epic.description:
            lines.append(f"- **Description:** {epic.description}")
        if epic.dependencies:
            lines.append(f"- **Dependencies:** {', '.join(epic.dependencies)}")
        if epic.risks:
            lines.append(f"- **Risks:** {', '.join(epic.risks)}")
        refs = format_source_references(epic.source_references)
        if refs:
            lines.append(f"- **Sources:** {refs}")
        lines.append("")

    lines.append("## 4. User Stories")
    if not plan.stories:
        lines.append("(none)")
    for story in plan.stories:
        lines.append(
            f"### {story.story_id}: {story.title} (Epic: {story.epic_id}) `[{story.classification}]`"
        )
        lines.append(f"As a {story.persona}, I want {story.story_statement}, so that {story.business_value}.")
        lines.append(f"- **Priority:** {story.priority}")
        if story.suggested_story_points is not None:
            lines.append(
                f"- **Suggested story points (unconfirmed estimate):** {story.suggested_story_points}"
            )
        lines.append("- **Acceptance criteria:**")
        for ac in story.acceptance_criteria:
            lines.append(f"  - {ac.criterion_id}: Given {ac.given} When {ac.when} Then {ac.then}")
        if story.dependencies:
            lines.append(f"- **Dependencies:** {', '.join(story.dependencies)}")
        if story.assumptions:
            lines.append(f"- **Assumptions:** {', '.join(story.assumptions)}")
        refs = format_source_references(story.source_references)
        if refs:
            lines.append(f"- **Sources:** {refs}")
        lines.append("")

    lines.append("## 5. Technical Tasks (recommendations, not confirmed requirements)")
    if not plan.technical_tasks:
        lines.append("(none)")
    for task in plan.technical_tasks:
        story_ref = f" (story {task.story_id})" if task.story_id else ""
        lines.append(f"- **{task.task_id}** [{task.category}]{story_ref}: {task.description}")

    lines += ["", "## 6. RAID Log", "### Risks"]
    if not plan.raid.risks:
        lines.append("(none)")
    for risk in plan.raid.risks:
        lines.append(
            f"- **{risk.risk_id}** [{risk.classification}] "
            f"({risk.probability}/{risk.impact}/{risk.severity}): {risk.description} — "
            f"Mitigation: {risk.mitigation}; Contingency: {risk.contingency}"
        )
    lines.append("### Assumptions")
    if not plan.raid.assumptions:
        lines.append("(none)")
    for assumption in plan.raid.assumptions:
        lines.append(f"- **{assumption.assumption_id}** [{assumption.classification}]: {assumption.description}")
    lines.append("### Issues")
    if not plan.raid.issues:
        lines.append("(none)")
    for issue in plan.raid.issues:
        lines.append(f"- **{issue.issue_id}** ({issue.status}): {issue.description}")
    lines.append("### Dependencies")
    if not plan.raid.dependencies:
        lines.append("(none)")
    for dep in plan.raid.dependencies:
        lines.append(
            f"- **{dep.dependency_id}** [{dep.dependency_type}]: {dep.blocking_item_id} blocks "
            f"{dep.blocked_item_id} — {dep.description or 'no description'}"
        )

    lines += ["", "## 7. Sprint Plan (AI-generated draft — requires human review)"]
    sprint_plan = plan.sprint_plan
    if sprint_plan is None:
        lines.append("(no sprint plan generated)")
    else:
        lines.append(f"- **Suggested sprint count:** {sprint_plan.suggested_sprint_count}")
        for sprint in sprint_plan.sprints:
            lines.append(
                f"### Sprint {sprint.sprint_number}: {sprint.sprint_goal} ({sprint.story_point_total} pts)"
            )
            lines.append(f"- Stories: {', '.join(sprint.story_ids) or '(none)'}")
        if sprint_plan.unscheduled_story_ids:
            lines.append(f"- **Unscheduled stories:** {', '.join(sprint_plan.unscheduled_story_ids)}")
        if sprint_plan.dependency_considerations:
            lines.append("- **Dependency considerations:** " + "; ".join(sprint_plan.dependency_considerations))

    lines += [
        "", "## 8. Traceability Matrix",
        "| Requirement | Source | Epic | Story | Acceptance Criteria |",
        "|---|---|---|---|---|",
    ]
    for row in plan.traceability.rows:
        source = format_source_references(row.source_references)
        lines.append(
            f"| {row.requirement_id} | {source} | {row.epic_id or ''} | {row.story_id or ''} | "
            f"{', '.join(row.acceptance_criterion_ids)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _project_export_dir(export_dir: Path, project_id: str) -> Path:
    project_dir = export_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def write_json_file(
    project_id: str, plan: ProjectPlan, *, approved: bool, export_dir: Path
) -> Path:
    path = _project_export_dir(export_dir, project_id) / "plan.json"
    path.write_text(json.dumps(build_json_export(plan, approved=approved), indent=2))
    return path


def write_markdown_file(
    project_id: str, plan: ProjectPlan, *, approved: bool, export_dir: Path
) -> Path:
    path = _project_export_dir(export_dir, project_id) / "plan.md"
    path.write_text(build_markdown_export(plan, approved=approved))
    return path


def write_jira_csv_file(project_id: str, plan: ProjectPlan, *, export_dir: Path) -> Path:
    path = _project_export_dir(export_dir, project_id) / "jira.csv"
    path.write_text(build_jira_csv_text(plan))
    return path


def write_reviewer_report_file(
    project_id: str, report: ReviewerReport, *, export_dir: Path
) -> Path:
    path = _project_export_dir(export_dir, project_id) / "reviewer_report.json"
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    return path


def build_zip_bytes(paths: dict[str, Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths.values():
            zf.write(path, arcname=path.name)
    return buf.getvalue()
