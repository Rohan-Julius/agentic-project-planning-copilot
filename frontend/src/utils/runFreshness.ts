/**
 * A `WorkflowEvent` with status IN_PROGRESS only means "genuinely happening right now" if
 * it was logged recently. The execution log is append-only and `WorkflowRun.status` only
 * updates when the graph invocation *returns* (app/workflow/engine.py::_sync_run) — if the
 * server process handling `/workflow/start` dies mid-call (e.g. restarted), nothing ever
 * calls that again, so the run stays frozen at RUNNING with a stale IN_PROGRESS event
 * forever. Nothing on the backend resumes it automatically (confirmed live: a stuck run
 * showed the exact same 3 events, unchanged, more than a day later across a server
 * restart). Without this check the UI has no way to tell "actively executing" apart from
 * "the last thing that happened before the process died" and renders both identically.
 */

// Generous on purpose: a single local LLM call can legitimately take minutes, and this
// only needs to catch runs that are dead, not flag every slow-but-healthy one.
export const STALE_EVENT_THRESHOLD_MS = 5 * 60 * 1000

export function isEventLive(
  timestamp: string,
  now: number,
  thresholdMs: number = STALE_EVENT_THRESHOLD_MS,
): boolean {
  const eventTime = new Date(timestamp).getTime()
  if (Number.isNaN(eventTime)) return false
  return now - eventTime < thresholdMs
}
