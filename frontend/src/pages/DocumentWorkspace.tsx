import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { IndexResult, Project, ProjectDocument, WorkflowRun } from '../types'

const ACTIVE_RUN_STATUSES = ['RUNNING', 'WAITING_FOR_HUMAN_INPUT']

export default function DocumentWorkspace() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [documents, setDocuments] = useState<ProjectDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [file, setFile] = useState<File | null>(null)
  const [uploadType, setUploadType] = useState('')
  const [uploading, setUploading] = useState(false)

  const [textName, setTextName] = useState('')
  const [textType, setTextType] = useState('')
  const [textContent, setTextContent] = useState('')
  const [savingText, setSavingText] = useState(false)

  const [starting, setStarting] = useState(false)
  const [activeRun, setActiveRun] = useState<WorkflowRun | null>(null)

  const [indexing, setIndexing] = useState(false)
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null)
  const [hasIndexed, setHasIndexed] = useState(false)

  function loadDocuments(id: string) {
    return api.get<ProjectDocument[]>(`/projects/${id}/documents`).then(setDocuments)
  }

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([api.get<Project>(`/projects/${projectId}`), loadDocuments(projectId)])
      .then(([p]) => setProject(p))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
    // A run may already be active from a previous visit (e.g. the user navigated away and
    // back) — only one workflow run may drive a project at a time (app/api/workflow.py
    // rejects a second start with 409), so the button must reflect that on load, not just
    // after this screen's own start click.
    api
      .get<WorkflowRun>(`/projects/${projectId}/workflow/status`)
      .then((run) => setActiveRun(ACTIVE_RUN_STATUSES.includes(run.status) ? run : null))
      .catch(() => setActiveRun(null))
  }, [projectId])

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId || !file) return
    setError(null)
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      await api.postForm(
        `/projects/${projectId}/documents?document_type=${encodeURIComponent(uploadType)}`,
        form,
      )
      setFile(null)
      setUploadType('')
      await loadDocuments(projectId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function handleTextSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId || !textName.trim() || !textContent.trim()) return
    setError(null)
    setSavingText(true)
    try {
      await api.post(`/projects/${projectId}/documents/text`, {
        document_name: textName.trim(),
        content: textContent,
        document_type: textType,
      })
      setTextName('')
      setTextType('')
      setTextContent('')
      await loadDocuments(projectId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setSavingText(false)
    }
  }

  async function handleDelete(documentId: string) {
    if (!projectId) return
    setError(null)
    try {
      await api.delete(`/projects/${projectId}/documents/${documentId}`)
      await loadDocuments(projectId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    }
  }

  async function handleIndex() {
    if (!projectId) return
    setError(null)
    setIndexing(true)
    try {
      const result = await api.post<IndexResult>(`/projects/${projectId}/index`, {})
      setIndexResult(result)
      // Indexing is idempotent server-side: a repeat call on already-indexed documents
      // correctly returns chunk_count 0 (nothing new to do), not a failure — so "no
      // per-document errors" is the right success signal here, not chunk_count itself.
      if (Object.keys(result.errors).length === 0) setHasIndexed(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setIndexing(false)
    }
  }

  function handleStartWorkflow() {
    if (!projectId) return
    setError(null)
    setStarting(true)
    // POST /workflow/start runs the agent graph synchronously on the backend and can take
    // a long time (a single live LLM call alone can take minutes) — it doesn't return until
    // the graph hits a human gate, completes, or errors. The WorkflowRun row is created as
    // the very first thing the backend does, before any of that slow work, so navigating to
    // the Agent Execution screen immediately (rather than awaiting this response) lets it
    // start polling /workflow/status and /workflow/events right away instead of leaving the
    // user staring at a static "Running…" button with no visibility for minutes at a time.
    api.post(`/projects/${projectId}/workflow/start`, {}).catch((err) => {
      console.error('workflow/start request failed', err)
    })
    navigate(`/projects/${projectId}/workflow`)
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Documents'}</h1>
          <p className="muted">Upload requirement documents or paste text (PDF, DOCX, TXT, Markdown).</p>
        </div>
        <Link className="back-link" to="/">
          ← Back to projects
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <>
          <section className="panel">
            <h2>Documents ({documents.length})</h2>
            {documents.length === 0 ? (
              <p>No documents yet. Upload a file or add text below.</p>
            ) : (
              <ul className="document-list">
                {documents.map((doc) => (
                  <li key={doc.document_id} className="document-row">
                    <div className="document-info">
                      <span className="document-name">{doc.document_name}</span>
                      <span className="document-meta">
                        v{doc.document_version} · {doc.document_type || 'uncategorized'} · {doc.status}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="button-danger"
                      onClick={() => handleDelete(doc.document_id)}
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <h2>Upload a file</h2>
            <form className="form" onSubmit={handleUpload}>
              <div className="field">
                <label htmlFor="file">File (PDF, DOCX, TXT, Markdown)</label>
                <input
                  id="file"
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="upload-type">Category</label>
                <input
                  id="upload-type"
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  placeholder="e.g. requirements, standards"
                />
              </div>
              <div className="form-actions">
                <button className="button" type="submit" disabled={!file || uploading}>
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
              </div>
            </form>
          </section>

          <section className="panel">
            <h2>Add text</h2>
            <form className="form" onSubmit={handleTextSubmit}>
              <div className="field">
                <label htmlFor="text-name">Document name</label>
                <input
                  id="text-name"
                  value={textName}
                  onChange={(e) => setTextName(e.target.value)}
                  placeholder="e.g. stakeholder-notes"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="text-type">Category</label>
                <input
                  id="text-type"
                  value={textType}
                  onChange={(e) => setTextType(e.target.value)}
                  placeholder="e.g. requirements, standards"
                />
              </div>
              <div className="field">
                <label htmlFor="text-content">Content</label>
                <textarea
                  id="text-content"
                  rows={6}
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  required
                />
              </div>
              <div className="form-actions">
                <button
                  className="button"
                  type="submit"
                  disabled={!textName.trim() || !textContent.trim() || savingText}
                >
                  {savingText ? 'Saving…' : 'Add document'}
                </button>
              </div>
            </form>
          </section>

          <section className="panel">
            <h2>Index documents</h2>
            <p className="muted">
              Documents must be indexed (chunked, embedded, and stored for retrieval) before
              requirement analysis can find anything in them. Re-run this after uploading new
              documents.
            </p>
            <div className="form-actions">
              <button
                className="button"
                type="button"
                onClick={handleIndex}
                disabled={indexing || documents.length === 0}
              >
                {indexing ? 'Indexing…' : 'Index documents'}
              </button>
            </div>
            {documents.length === 0 && (
              <p className="muted">Upload at least one document first.</p>
            )}
            {indexResult && (
              <p className="muted">
                Indexed {indexResult.indexed_document_ids.length} document(s),{' '}
                {indexResult.chunk_count} chunk(s).
                {Object.keys(indexResult.errors).length > 0 &&
                  ` Errors: ${Object.values(indexResult.errors).join('; ')}`}
              </p>
            )}
          </section>

          <section className="panel">
            <h2>Requirement analysis</h2>
            <p className="muted">
              Once your documents are indexed, run requirement analysis to extract
              requirements and generate clarification questions.
            </p>
            <div className="form-actions">
              <button
                className="button"
                type="button"
                onClick={handleStartWorkflow}
                disabled={starting || !hasIndexed || !!activeRun}
              >
                {starting ? 'Running…' : 'Run requirement analysis'}
              </button>
              {activeRun && (
                <Link className="button" to={`/projects/${projectId}/workflow`}>
                  View agent execution →
                </Link>
              )}
            </div>
            {!hasIndexed && !activeRun && (
              <p className="muted">Index your documents first (see above).</p>
            )}
            {activeRun && (
              <p className="muted">
                A workflow run is already {activeRun.status} for this project — wait for it to
                reach a human gate or finish before starting another.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
