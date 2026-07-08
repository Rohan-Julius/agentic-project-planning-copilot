"""Day 2 sanity test: ORM models create tables and round-trip a row (spec §19, §22)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, ProjectRecord, RequirementRecord, WorkflowEvent, WorkflowRun


def test_models_create_all_tables_and_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        project = ProjectRecord(project_id="PRJ-001", name="Leave Management")
        session.add(project)
        session.commit()

        req = RequirementRecord(
            requirement_id="REQ-1",
            project_id="PRJ-001",
            title="Login",
            category="functional",
            classification="SOURCE_BACKED",
            confidence=0.9,
            payload_json={"description": "Users can log in"},
        )
        session.add(req)

        run = WorkflowRun(workflow_run_id="RUN-101", project_id="PRJ-001")
        session.add(run)
        session.commit()

        event = WorkflowEvent(
            workflow_run_id="RUN-101",
            project_id="PRJ-001",
            agent="RequirementAnalystAgent",
            action="search_project_documents",
            status="SUCCESS",
            result_count=5,
            duration_ms=420,
        )
        session.add(event)
        session.commit()

        assert session.query(ProjectRecord).filter_by(project_id="PRJ-001").one().name == (
            "Leave Management"
        )
        assert session.query(RequirementRecord).count() == 1
        assert session.query(WorkflowEvent).one().action == "search_project_documents"


def test_project_methodology_defaults_to_agile_scrum():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        session.add(ProjectRecord(project_id="PRJ-002", name="X"))
        session.commit()
        assert session.query(ProjectRecord).one().methodology == "agile_scrum"
