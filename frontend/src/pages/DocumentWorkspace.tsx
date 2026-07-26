import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Project, ProjectDocument, WorkflowRun } from '../types'

export default function DocumentWorkspace() {
  const { projectId } = useParams<{ projectId: string }>()
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
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null)

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

  async function handleStartWorkflow() {
    if (!projectId) return
    setError(null)
    setStarting(true)
    try {
      const run = await api.post<WorkflowRun>(`/projects/${projectId}/workflow/start`, {})
      setWorkflowStatus(run.status)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setStarting(false)
    }
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
            <h2>Requirement analysis</h2>
            <p className="muted">
              Once your documents are uploaded, run requirement analysis to extract
              requirements and generate clarification questions.
            </p>
            <div className="form-actions">
              <button
                className="button"
                type="button"
                onClick={handleStartWorkflow}
                disabled={starting || documents.length === 0}
              >
                {starting ? 'Running…' : 'Run requirement analysis'}
              </button>
              {workflowStatus && (
                <Link className="button" to={`/projects/${projectId}/workflow`}>
                  View agent execution →
                </Link>
              )}
            </div>
            {documents.length === 0 && (
              <p className="muted">Upload at least one document first.</p>
            )}
            {workflowStatus && <p className="muted">Workflow status: {workflowStatus}</p>}
          </section>
        </>
      )}
    </div>
  )
}
