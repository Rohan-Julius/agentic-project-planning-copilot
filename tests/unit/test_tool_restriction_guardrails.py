"""Tool & filesystem restriction guardrail tests (spec §20.2) — no shell/eval/exec surface
anywhere in app/, no dynamic tool-calling exposed to the LLM, and document uploads can never
write outside the project data directory regardless of the supplied filename.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.runner import run_agent
from app.config import Settings
from app.models.base import Base
from app.services.document_service import save_uploaded_document
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

# Substrings that would indicate a shell/arbitrary-code-execution surface exists. Checked as
# plain substrings (not regex) — deliberately conservative, over-matching is fine here (a
# false positive just means manually confirming a hit is safe, never masks a real one).
_DANGEROUS_PATTERNS = ("subprocess", "os.system(", "os.popen(", "eval(", "exec(", "shell=True")


def test_no_shell_or_arbitrary_code_execution_surface_in_app_source():
    """§20.2: 'No shell-execution tool' / 'No arbitrary Python-execution tool'. A source
    scan rather than a runtime test — the guarantee is that the *capability* doesn't exist
    anywhere in app/, not just that no currently-registered tool happens to use it.
    """
    offending: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in text:
                offending.append(f"{path.relative_to(APP_ROOT.parent)}: contains '{pattern}'")

    assert offending == [], "\n".join(offending)


class _EchoDecision(BaseModel):
    action: str


def test_run_agent_tools_parameter_never_reaches_ollama():
    """§20.2: agents 'must only use registered tools' — in this architecture there is no
    dynamic tool-calling at all (retrieval is a hardcoded Python call made *before* the LLM
    is invoked, never something the model chooses). Proves that by construction: even if a
    dangerous callable is passed as `tools=`, run_agent() never invokes it and never forwards
    it to ollama.generate.
    """
    dangerous_calls: list[str] = []

    def _dangerous_tool() -> str:
        dangerous_calls.append("called")
        return "should never run"

    mock_response = {"response": '{"action": "ok"}'}
    with patch("ollama.generate", return_value=mock_response) as mock_generate:
        result = run_agent(
            agent_name="test",
            prompt="Decide",
            output_model=_EchoDecision,
            tools=[_dangerous_tool],
        )

    assert result.action == "ok"
    assert dangerous_calls == []
    assert "tools" not in mock_generate.call_args.kwargs


def test_uploaded_document_path_traversal_filename_stays_inside_documents_dir(tmp_path):
    """§20.2: 'File-system access should be restricted to the project data directory.' The
    on-disk path is built from a server-generated document_id, never the user-supplied
    filename, so a path-traversal attempt in the filename can only ever contribute its
    (validated) extension — this proves that invariant holds end-to-end through the real
    save path, not just by reading the source.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    settings = Settings(_env_file=None, DATA_DIR=str(tmp_path))

    from app.models.project import ProjectRecord

    with session_factory() as session:
        session.add(ProjectRecord(project_id="proj_traversal", name="Traversal Test"))
        session.commit()

        malicious_filename = "../../../../etc/evil.txt"
        document = save_uploaded_document(
            session, settings, "proj_traversal", malicious_filename, b"malicious content"
        )

    stored_path = Path(document.file_path).resolve()
    assert stored_path.is_relative_to(settings.documents_dir.resolve())
    # The literal attacker-controlled path components must never have been used.
    assert ".." not in stored_path.parts
    assert not (tmp_path.parent / "etc" / "evil.txt").exists()
