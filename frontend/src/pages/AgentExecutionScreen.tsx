import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import HoverButtonContent from "../components/HoverButtonContent";
import type { Project, WorkflowEvent, WorkflowRun } from "../types";
import { isEventLive } from "../utils/runFreshness";
import {
  agentLabel,
  eventActivityLabel,
  logRowStatusLabel,
  runStatusLabel,
  stageLabel,
} from "../utils/workflowLabels";

// Keyed by `WorkflowRun.pending_gate` (app/api/workflow.py `/workflow/status`, backed by
// engine.get_pending_gate_stage reading the interrupt's own `{"stage": ...}` payload) — a
// deterministic signal, not the Supervisor's advisory `RECOMMEND_*` recommendation. That
// recommendation is a separate LLM call that proved unreliable at picking the right action
// for more than one state transition (found live, twice) and is kept in the execution log
// purely for audit/debugging, never for navigation.
// final_gate routes to /plan first, not straight to /review — the intended flow is
// Execution screen → Plan (read the full generated plan) → Reviewer findings → Approve.
// PlanningWorkspace's own header already links forward to /review ("Reviewer findings →"),
// so this just makes that the entry point instead of skipping straight to approval.
const GATE_LINKS: Record<string, { label: string; to: string }> = {
  clarification_gate: {
    label: "Answer clarification questions",
    to: "clarifications",
  },
  final_gate: { label: "Review the plan and approve", to: "plan" },
};

const GATE_DESCRIPTIONS: Record<string, string> = {
  clarification_gate:
    "The Requirement Analyst found questions it cannot resolve from the documents alone.",
  final_gate:
    "A plan has been generated and reviewed. It will not be exported as approved until you say so.",
};

// The four real agents (spec §7) — "Workflow" events (gate resume, completion, controlled
// stop) are the engine's own bookkeeping, not an agent acting, so they don't get a node here.
const AGENT_KEYS = ["Supervisor", "RequirementAnalyst", "Planning", "Reviewer"];

export default function AgentExecutionScreen() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [abandoning, setAbandoning] = useState(false);
  const [replayIndex, setReplayIndex] = useState<number | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api
      .get<Project>(`/projects/${projectId}`)
      .then(setProject)
      .catch(() => undefined);

    let cancelled = false;
    function poll() {
      Promise.all([
        api.get<WorkflowRun>(`/projects/${projectId}/workflow/status`),
        api.get<WorkflowEvent[]>(`/projects/${projectId}/workflow/events`),
      ])
        .then(([r, e]) => {
          if (cancelled) return;
          setRun(r);
          setEvents(e);
          setError(null);
        })
        .catch((err) => {
          if (!cancelled)
            setError(
              err instanceof ApiError ? err.message : (err as Error).message,
            );
        });
    }
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [projectId]);

  // Replay playback: steps replayIndex forward on a timer while playing. Deliberately scoped
  // to the events already fetched for this (the latest) run — GET .../workflow/events is
  // itself scoped to one run's history, not a jumbled cross-run log (see that endpoint's own
  // docstring), so replay doesn't reach past that.
  useEffect(() => {
    if (!replayPlaying || replayIndex === null) return;
    if (replayIndex >= events.length - 1) {
      setReplayPlaying(false);
      return;
    }
    const timer = setTimeout(() => setReplayIndex((i) => (i === null ? null : i + 1)), 800);
    return () => clearTimeout(timer);
  }, [replayPlaying, replayIndex, events.length]);

  async function handleAbandon() {
    if (!projectId) return;
    setError(null);
    setAbandoning(true);
    try {
      const updatedRun = await api.post<WorkflowRun>(
        `/projects/${projectId}/workflow/abandon`,
        {},
      );
      setRun(updatedRun);
      // Refresh so the ABANDONED event this just logged shows up immediately, instead of
      // waiting up to 3s for the next poll tick.
      const updatedEvents = await api.get<WorkflowEvent[]>(
        `/projects/${projectId}/workflow/events`,
      );
      setEvents(updatedEvents);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setAbandoning(false);
    }
  }

  // WorkflowRun.status only updates when a graph invocation *returns* — after a human
  // approves a gate, the backend resumes and keeps running (Planning, Reviewer, ...)
  // without touching `status` until it returns again, so `status` stays stuck at
  // WAITING_FOR_HUMAN_INPUT for that whole stretch. What's actually true mid-run is only
  // whichever event was logged *last overall* — if it's IN_PROGRESS, the graph is still
  // working regardless of what the stale `status` says.
  //
  // But IN_PROGRESS alone isn't enough either: the execution log is append-only, and
  // nothing on the backend automatically resumes a run whose owning process died mid-call
  // (confirmed live — a stuck run showed the same 3 events, unchanged, more than a day
  // later across a server restart). So an IN_PROGRESS event only counts as genuinely live
  // if it's recent; otherwise this is a stalled run, not a running one, and the UI must
  // not claim it's actively happening.
  const latestEvent = events[events.length - 1];
  const latestEventIsFresh = latestEvent
    ? isEventLive(latestEvent.timestamp, Date.now())
    : false;
  const isRunning = latestEvent?.status === "IN_PROGRESS" && latestEventIsFresh;
  const isStalled = latestEvent?.status === "IN_PROGRESS" && !latestEventIsFresh;
  const activeAgent = isRunning ? latestEvent.agent : null;

  const completedAgents = new Set(
    events
      .filter((e) => e.status === "SUCCESS" && AGENT_KEYS.includes(e.agent))
      .map((e) => e.agent),
  );

  const gateLink = run?.pending_gate ? GATE_LINKS[run.pending_gate] : undefined;
  const gateDescription = run?.pending_gate
    ? GATE_DESCRIPTIONS[run.pending_gate]
    : undefined;

  const isReplaying = replayIndex !== null;
  const visibleEvents = isReplaying ? events.slice(0, replayIndex + 1) : events;
  const replayCurrentEvent = isReplaying ? events[replayIndex] : null;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? "Agent execution"}</h1>
          <p className="muted">
            Safe execution summary: never the model's hidden reasoning.
          </p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/documents`}>
          ← Back to documents
        </Link>
      </header>

      {error && <p className="error">{error}</p>}
      {!run && !error && (
        <p>
          No workflow run yet. Start requirement analysis from the document
          workspace.
        </p>
      )}

      {run && (
        <>
          <ol className="agent-row" aria-label="Agents">
            {AGENT_KEYS.map((key) => (
              <li
                key={key}
                className={`agent-node${key === activeAgent ? " is-active" : ""}${
                  completedAgents.has(key) ? " is-done" : ""
                }`}
              >
                <span className="agent-dot" aria-hidden="true" />
                {agentLabel(key)}
              </li>
            ))}
          </ol>

          <section className="panel">
            <h2>
              Status:{" "}
              {isRunning
                ? `${agentLabel(latestEvent.agent)}: ${eventActivityLabel(latestEvent)}`
                : isStalled
                  ? "Possibly stalled"
                  : runStatusLabel(run.status)}
            </h2>
            <p className="muted">
              Run {run.workflow_run_id} · revision count {run.revision_count} ·
              final approved: {String(run.final_approved)}
            </p>
            {run.status === "COMPLETED" && (
              <Link
                className="button-hover"
                to={`/projects/${projectId}/export`}
              >
                <HoverButtonContent>View export</HoverButtonContent>
              </Link>
            )}
          </section>

          {isStalled && (
            <div className="panel">
              <p className="error">
                No activity for over 5 minutes. This usually means the server was
                restarted (or otherwise stopped) while this run was still working, and
                nothing here resumes automatically. If you don't expect it to still be
                working, mark it as failed so this project can start a new run.
              </p>
              <div className="form-actions">
                <button
                  className="button-danger"
                  type="button"
                  onClick={handleAbandon}
                  disabled={abandoning}
                >
                  {abandoning ? "Marking as failed…" : "Mark as failed"}
                </button>
              </div>
            </div>
          )}

          {gateLink && (
            <div className="gate-seal">
              <p className="gate-seal-eyebrow">◈ Workflow paused: needs you</p>
              <p className="gate-seal-desc">{gateDescription}</p>
              <Link
                className="button-hover"
                to={`/projects/${projectId}/${gateLink.to}`}
              >
                <HoverButtonContent>{gateLink.label}</HoverButtonContent>
              </Link>
            </div>
          )}

          <section className="panel">
            <h2>Execution log ({events.length})</h2>
            {events.length > 1 && (
              <div className="replay-controls">
                {!isReplaying ? (
                  <button
                    type="button"
                    className="button-hover"
                    onClick={() => {
                      setReplayIndex(0);
                      setReplayPlaying(false);
                    }}
                  >
                    Replay from the start
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="button-hover"
                      onClick={() => setReplayPlaying((p) => !p)}
                    >
                      {replayPlaying ? "Pause" : "Play"}
                    </button>
                    <button
                      type="button"
                      className="button-hover"
                      disabled={replayIndex === 0}
                      onClick={() => setReplayIndex((i) => Math.max(0, (i ?? 0) - 1))}
                    >
                      ← Step back
                    </button>
                    <button
                      type="button"
                      className="button-hover"
                      disabled={replayIndex === events.length - 1}
                      onClick={() =>
                        setReplayIndex((i) => Math.min(events.length - 1, (i ?? 0) + 1))
                      }
                    >
                      Step forward →
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={events.length - 1}
                      value={replayIndex ?? 0}
                      onChange={(e) => setReplayIndex(Number(e.target.value))}
                      aria-label="Replay position"
                    />
                    <span className="muted">
                      {(replayIndex ?? 0) + 1} / {events.length}
                      {replayCurrentEvent
                        ? ` — ${agentLabel(replayCurrentEvent.agent)}: ${eventActivityLabel(replayCurrentEvent)}`
                        : ""}
                    </span>
                    <button
                      type="button"
                      className="button-hover"
                      onClick={() => {
                        setReplayIndex(null);
                        setReplayPlaying(false);
                      }}
                    >
                      Exit replay
                    </button>
                  </>
                )}
              </div>
            )}
            <ul className="log">
              {visibleEvents.map((event, i) => {
                const isLive = event === latestEvent && isRunning;
                return (
                  <li
                    key={i}
                    className={`log-row${event.status === "ERROR" ? " log-row-error" : ""}`}
                    style={{ animationDelay: `${Math.min(i, 20) * 30}ms` }}
                  >
                    <span
                      className={`log-status-dot log-status-${event.status.toLowerCase()}${
                        isLive ? " is-live" : ""
                      }`}
                      aria-hidden="true"
                    />
                    <span className="log-time">
                      {formatTime(event.timestamp)}
                    </span>
                    <span className="log-agent">{agentLabel(event.agent)}</span>
                    <span
                      className={`log-action${isLive ? " shine-text" : ""}`}
                    >
                      {eventActivityLabel(event)}
                    </span>
                    <span className="muted log-meta">
                      {stageLabel(event.stage)} ·{" "}
                      {logRowStatusLabel(event.status, isLive)}
                    </span>
                    {event.error && <p className="error">{event.error}</p>}
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function formatTime(timestamp: string): string {
  const d = new Date(timestamp);
  return Number.isNaN(d.getTime()) ? timestamp : d.toLocaleTimeString();
}
