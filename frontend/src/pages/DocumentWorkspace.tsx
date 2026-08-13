import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import FileUpload from '../components/FileUpload'
import ShinyButton from '../components/ShinyButton'
import type {
  DocumentChunk,
  IndexResult,
  ParsedDocument,
  Project,
  ProjectDocument,
  WorkflowRun,
} from '../types'
import { runStatusLabel } from '../utils/workflowLabels'

type DetailView = 'text' | 'chunks'

const ACTIVE_RUN_STATUSES = ['RUNNING', 'WAITING_FOR_HUMAN_INPUT']

export default function DocumentWorkspace() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [documents, setDocuments] = useState<ProjectDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [files, setFiles] = useState<File[]>([])
  const [uploadType, setUploadType] = useState('')
  const [uploading, setUploading] = useState(false)

  const [textName, setTextName] = useState('')
  const [textType, setTextType] = useState('')
  const [textContent, setTextContent] = useState('')
  const [savingText, setSavingText] = useState(false)

  const [starting, setStarting] = useState(false)
  const [activeRun, setActiveRun] = useState<WorkflowRun | null>(null)

  const [indexing, setIndexing] = useState(false)
  const [forceIndexing, setForceIndexing] = useState(false)
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null)
  // Derived from the real per-document status the backend already tracks
  // (indexing_service.INDEXED_STATUS), not separate client-side state — that way it's
  // correct on first load even if these documents were indexed in an earlier session,
  // and never needs a redundant "click Index to unlock analysis" step.
  const hasIndexed = documents.some((doc) => doc.status === 'INDEXED')

  const [expandedDoc, setExpandedDoc] = useState<{ id: string; view: DetailView } | null>(null)
  const [textCache, setTextCache] = useState<Record<string, ParsedDocument>>({})
  const [chunksCache, setChunksCache] = useState<Record<string, DocumentChunk[]>>({})
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

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
    if (!projectId || files.length === 0) return
    setError(null)
    setUploading(true)
    // The backend accepts one file per request, so a multi-file drop uploads sequentially.
    // One bad file (wrong format, duplicate name, etc.) shouldn't block the rest of the
    // batch — collect failures and keep going, then surface them together at the end.
    const failures: string[] = []
    for (const uploadFile of files) {
      const form = new FormData()
      form.append('file', uploadFile)
      try {
        await api.postForm(
          `/projects/${projectId}/documents?document_type=${encodeURIComponent(uploadType)}`,
          form,
        )
      } catch (err) {
        const message = err instanceof ApiError ? err.message : (err as Error).message
        failures.push(`${uploadFile.name}: ${message}`)
      }
    }
    setFiles([])
    setUploadType('')
    await loadDocuments(projectId)
    if (failures.length > 0) {
      setError(`Some files failed to upload: ${failures.join('; ')}`)
    }
    setUploading(false)
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
      if (expandedDoc?.id === documentId) setExpandedDoc(null)
      await loadDocuments(projectId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    }
  }

  async function runIndex(force: boolean) {
    if (!projectId) return
    setError(null)
    if (force) setForceIndexing(true)
    else setIndexing(true)
    try {
      const result = await api.post<IndexResult>(`/projects/${projectId}/index?force=${force}`, {})
      setIndexResult(result)
      // Refresh so each document's real status (INDEXED, INDEX_ERROR, ...) is up to date —
      // hasIndexed is derived from this list, and the status column shown per document
      // would otherwise stay stale ("UPLOADED") even after a successful index.
      await loadDocuments(projectId)
      // A (forced) re-index rewrites chunk text — any chunk lists already fetched for this
      // panel are stale now, so drop the cache rather than keep showing outdated content.
      if (force) setChunksCache({})
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      if (force) setForceIndexing(false)
      else setIndexing(false)
    }
  }

  function handleIndex() {
    return runIndex(false)
  }

  function handleForceReindex() {
    return runIndex(true)
  }

  async function toggleDetail(documentId: string, view: DetailView) {
    if (!projectId) return
    if (expandedDoc?.id === documentId && expandedDoc.view === view) {
      setExpandedDoc(null)
      return
    }
    setExpandedDoc({ id: documentId, view })
    setDetailError(null)
    const alreadyCached = view === 'text' ? documentId in textCache : documentId in chunksCache
    if (alreadyCached) return
    setDetailLoading(true)
    try {
      if (view === 'text') {
        const parsed = await api.get<ParsedDocument>(
          `/projects/${projectId}/documents/${documentId}/text`,
        )
        setTextCache((prev) => ({ ...prev, [documentId]: parsed }))
      } else {
        const chunks = await api.get<DocumentChunk[]>(
          `/projects/${projectId}/documents/${documentId}/chunks`,
        )
        setChunksCache((prev) => ({ ...prev, [documentId]: chunks }))
      }
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setDetailLoading(false)
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
          <p className="muted">
            Upload requirement documents (PDF, DOCX, TXT, or Markdown) or paste text directly.
          </p>
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
                {documents.map((doc) => {
                  const isExpanded = expandedDoc?.id === doc.document_id
                  const view = isExpanded ? expandedDoc.view : null
                  return (
                    <li key={doc.document_id} className="document-item">
                      <div className="document-row">
                        <div className="document-info">
                          <span className="document-name">{doc.document_name}</span>
                          <span className="document-meta">
                            v{doc.document_version} · {doc.document_type || 'uncategorized'} ·{' '}
                            {doc.status}
                          </span>
                        </div>
                        <div className="document-actions">
                          <button
                            type="button"
                            className={`button-ghost${view === 'text' ? ' is-active' : ''}`}
                            onClick={() => toggleDetail(doc.document_id, 'text')}
                          >
                            View text
                          </button>
                          <button
                            type="button"
                            className={`button-ghost${view === 'chunks' ? ' is-active' : ''}`}
                            onClick={() => toggleDetail(doc.document_id, 'chunks')}
                          >
                            View chunks
                          </button>
                          <button
                            type="button"
                            className="button-danger"
                            onClick={() => handleDelete(doc.document_id)}
                          >
                            Delete
                          </button>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="document-detail">
                          {detailLoading && <p className="muted">Loading…</p>}
                          {detailError && <p className="error">{detailError}</p>}
                          {!detailLoading && !detailError && view === 'text' && (
                            <DocumentTextDetail parsed={textCache[doc.document_id]} />
                          )}
                          {!detailLoading && !detailError && view === 'chunks' && (
                            <DocumentChunksDetail chunks={chunksCache[doc.document_id]} />
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          <section className="panel">
            <h2>Upload files</h2>
            <form className="form" onSubmit={handleUpload}>
              <FileUpload
                files={files}
                onFilesChange={setFiles}
                accept=".pdf,.docx,.txt,.md"
                hint="PDF, DOCX, TXT, or Markdown"
                disabled={uploading}
              />
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
                <button className="button" type="submit" disabled={files.length === 0 || uploading}>
                  {uploading
                    ? 'Uploading…'
                    : files.length > 1
                      ? `Upload ${files.length} files`
                      : 'Upload'}
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
              Documents must be indexed before requirement analysis can use them. "Index
              documents" only processes new files; use "Force re-index all" to rebuild
              everything from scratch.
            </p>
            <div className="form-actions">
              <button
                className="button"
                type="button"
                onClick={handleIndex}
                disabled={indexing || forceIndexing || documents.length === 0}
              >
                {indexing ? 'Indexing…' : 'Index documents'}
              </button>
              <button
                className="button-ghost"
                type="button"
                onClick={handleForceReindex}
                disabled={indexing || forceIndexing || documents.length === 0}
              >
                {forceIndexing ? 'Re-indexing…' : 'Force re-index all'}
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
              {activeRun ? (
                // A run is already active — this button is no longer the actionable one, so
                // it goes static instead of shimmering while disabled (which would look
                // actionable when it isn't). The shiny "make it happen" treatment doesn't
                // disappear, though — it moves to "View agent execution" below, since
                // that's now the button that actually leads to watching results happen.
                <button className="button-ghost" type="button" disabled>
                  Run requirement analysis
                </button>
              ) : (
                <ShinyButton
                  type="button"
                  onClick={handleStartWorkflow}
                  disabled={starting || !hasIndexed}
                >
                  {starting ? 'Running…' : 'Run requirement analysis'}
                </ShinyButton>
              )}
              {activeRun && (
                <Link className="button-shiny" to={`/projects/${projectId}/workflow`}>
                  <span>View agent execution</span>
                </Link>
              )}
            </div>
            {!hasIndexed && !activeRun && (
              <p className="muted">Index your documents first (see above).</p>
            )}
            {activeRun && (
              <p className="muted">
                A workflow run is already {runStatusLabel(activeRun.status).toLowerCase()} for
                this project. Wait for it to reach a human gate or finish before starting
                another.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  )
}

function DocumentTextDetail({ parsed }: { parsed: ParsedDocument | undefined }) {
  if (!parsed) return null
  if (parsed.blocks.length === 0) return <p className="muted">No extractable text.</p>
  return (
    <>
      {parsed.blocks.map((block, i) => (
        <div key={i} className="document-detail-entry">
          <p className="document-detail-entry-meta">
            {block.heading_level ? `Heading ${block.heading_level}` : 'Body'}
            {block.page_number ? ` · p.${block.page_number}` : ''}
            {block.section_hierarchy_path ? ` · ${block.section_hierarchy_path}` : ''}
          </p>
          <p className="document-detail-entry-text">{block.text}</p>
        </div>
      ))}
    </>
  )
}

function DocumentChunksDetail({ chunks }: { chunks: DocumentChunk[] | undefined }) {
  if (!chunks) return null
  if (chunks.length === 0) {
    return <p className="muted">Not indexed yet. Run indexing below to generate chunks.</p>
  }
  return (
    <>
      {chunks.map((chunk) => (
        <div key={chunk.chunk_id} className="document-detail-entry">
          <p className="document-detail-entry-meta">
            {chunk.chunk_id}
            {chunk.page_number ? ` · p.${chunk.page_number}` : ''}
            {chunk.section ? ` · ${chunk.section}` : ''}
          </p>
          <p className="document-detail-entry-text">{chunk.text}</p>
        </div>
      ))}
    </>
  )
}
