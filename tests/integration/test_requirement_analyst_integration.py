"""Integration tests for Requirement Analyst Agent workflow (Day 9)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, ProjectRecord, RequirementRecord
from app.schemas.requirement import RequirementAnalysisResult, Requirement
from app.tools.project_tools import save_requirements


def test_requirement_analyst_saves_and_retrieves():
    """Requirement Analyst saves requirements and they can be retrieved."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Setup: create project
    with SessionLocal() as session:
        project = ProjectRecord(
            project_id="PRJ-INT-001",
            name="Integration Test",
            description="",
            methodology="agile_scrum"
        )
        session.add(project)
        session.commit()

    # Create mock analysis result
    result = RequirementAnalysisResult(
        requirements=[
            Requirement(
                requirement_id="REQ-INT-001",
                title="Test Requirement",
                description="A requirement for testing",
                category="functional",
                classification="SOURCE_BACKED",
                confidence=0.9,
                source_references=[]
            )
        ],
        actors=[],
        missing_information=[],
        contradictions=[],
        ambiguities=[],
        clarification_questions=[]
    )

    # Save via tool
    save_requirements(
        project_id="PRJ-INT-001",
        analysis_result=result,
        workflow_run_id="RUN-INT-001",
        session_factory=SessionLocal
    )

    # Retrieve and verify
    with SessionLocal() as session:
        req = session.query(RequirementRecord).filter_by(
            project_id="PRJ-INT-001"
        ).first()

    assert req is not None
    assert req.requirement_id == "REQ-INT-001"
    assert req.title == "Test Requirement"


def test_requirement_analyst_project_isolation():
    """Requirements from one project don't leak to another."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Create two projects
    with SessionLocal() as session:
        for pid in ["PRJ-ISO-A", "PRJ-ISO-B"]:
            project = ProjectRecord(
                project_id=pid,
                name=f"Project {pid}",
                description="",
                methodology="agile_scrum"
            )
            session.add(project)
        session.commit()

    # Save requirement for PRJ-ISO-A
    result_a = RequirementAnalysisResult(
        requirements=[
            Requirement(
                requirement_id="REQ-A-001",
                title="Project A Requirement",
                description="",
                category="functional",
                classification="SOURCE_BACKED",
                confidence=0.9,
                source_references=[]
            )
        ],
        actors=[],
        missing_information=[],
        contradictions=[],
        ambiguities=[],
        clarification_questions=[]
    )
    save_requirements("PRJ-ISO-A", result_a, "RUN-A", session_factory=SessionLocal)

    # Save requirement for PRJ-ISO-B
    result_b = RequirementAnalysisResult(
        requirements=[
            Requirement(
                requirement_id="REQ-B-001",
                title="Project B Requirement",
                description="",
                category="functional",
                classification="SOURCE_BACKED",
                confidence=0.9,
                source_references=[]
            )
        ],
        actors=[],
        missing_information=[],
        contradictions=[],
        ambiguities=[],
        clarification_questions=[]
    )
    save_requirements("PRJ-ISO-B", result_b, "RUN-B", session_factory=SessionLocal)

    # Verify isolation
    with SessionLocal() as session:
        reqs_a = session.query(RequirementRecord).filter_by(project_id="PRJ-ISO-A").all()
        reqs_b = session.query(RequirementRecord).filter_by(project_id="PRJ-ISO-B").all()

    assert len(reqs_a) == 1
    assert reqs_a[0].requirement_id == "REQ-A-001"
    assert len(reqs_b) == 1
    assert reqs_b[0].requirement_id == "REQ-B-001"
