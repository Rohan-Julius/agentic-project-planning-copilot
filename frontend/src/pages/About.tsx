import Terminal from '../components/Terminal'

const SETUP_LINES = [
  { command: 'cp .env.example .env' },
  { text: '✔ Local config ready', tone: 'success' as const },
  { command: 'pip install -e ".[dev]"' },
  { text: '✔ Backend dependencies installed', tone: 'success' as const },
  { command: 'ollama pull qwen3:4b-instruct' },
  { text: '✔ Local LLM ready, no API key needed', tone: 'success' as const },
  { command: 'uvicorn app.main:app --reload' },
  { text: '✔ API running at http://localhost:8000', tone: 'success' as const },
  { command: 'cd frontend && npm install && npm run dev' },
  { text: '✔ Frontend running at http://localhost:5173', tone: 'success' as const },
  { text: 'Open http://localhost:5173 to get started.', tone: 'muted' as const },
]

export default function About() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>About</h1>
          <p className="muted">What Planning Copilot is, and how to run it.</p>
        </div>
      </header>

      <section className="panel">
        <h2>What this is</h2>
        <p>
          Planning Copilot turns a raw requirements document into a reviewable
          project-planning package (epics, user stories, acceptance criteria, tasks,
          dependencies, a RAID log, and a sprint plan), exportable to Markdown, JSON, and
          Jira-compatible CSV.
        </p>
        <p>
          It's a local, open-source proof of concept: everything runs on your own machine,
          powered by a local LLM, with no paid API and nothing sent to the cloud.
        </p>
      </section>

      <section className="panel">
        <h2>Run it locally</h2>
        <p className="section-subtitle">
          No paid API, no cloud service: just a local LLM (via Ollama) and a local vector
          store. Five commands from a clean checkout:
        </p>
        <Terminal
          label="Setting up and running Planning Copilot locally"
          lines={SETUP_LINES}
          className="about-setup-terminal"
        />
      </section>
    </div>
  )
}
