import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import FileUpload from '../components/FileUpload'
import type { IndexResult, OrganizationalDocument } from '../types'

/** Organizational-knowledge management (app/api/standards.py) — deliberately its own
 * top-level page, not folded into a project's Document workspace: these documents have no
 * project_id at all (see OrganizationalDocument), shared across every project the same way
 * "Projects" and "About" are also global destinations, not nested under any one project. */
export default function Standards() {
  const [documents, setDocuments] = useState<OrganizationalDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [files, setFiles] = useState<File[]>([])
  const [uploadType, setUploadType] = useState('')
  const [uploading, setUploading] = useState(false)

  const [textName, setTextName] = useState('')
  const [textType, setTextType] = useState('')
  const [textContent, setTextContent] = useState('')
  const [savingText, setSavingText] = useState(false)

  const [indexing, setIndexing] = useState(false)
  const [forceIndexing, setForceIndexing] = useState(false)
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null)

  function loadDocuments() {
    return api.get<OrganizationalDocument[]>('/organizational-documents').then(setDocuments)
  }

  useEffect(() => {
    setLoading(true)
    loadDocuments()
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault()
    if (files.length === 0) return
    setError(null)
    setUploading(true)
    const failures: string[] = []
    for (const uploadFile of files) {
      const form = new FormData()
      form.append('file', uploadFile)
      try {
        await api.postForm(
          `/organizational-documents?document_type=${encodeURIComponent(uploadType)}`,
          form,
        )
      } catch (err) {
        const message = err instanceof ApiError ? err.message : (err as Error).message
        failures.push(`${uploadFile.name}: ${message}`)
      }
    }
    setFiles([])
    setUploadType('')
    await loadDocuments()
    if (failures.length > 0) {
      setError(`Some standards files failed to upload: ${failures.join('; ')}`)
    }
    setUploading(false)
  }

  async function handleTextSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!textName.trim() || !textContent.trim()) return
    setError(null)
    setSavingText(true)
    try {
      await api.post('/organizational-documents/text', {
        document_name: textName.trim(),
        content: textContent,
        document_type: textType,
      })
      setTextName('')
      setTextType('')
      setTextContent('')
      await loadDocuments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setSavingText(false)
    }
  }

  async function handleDelete(documentId: string) {
    setError(null)
    try {
      await api.delete(`/organizational-documents/${documentId}`)
      await loadDocuments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    }
  }

  async function runIndex(force: boolean) {
    setError(null)
    if (force) setForceIndexing(true)
    else setIndexing(true)
    try {
      const result = await api.post<IndexResult>(`/organizational-documents/index?force=${force}`, {})
      setIndexResult(result)
      await loadDocuments()
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

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Company standards</h1>
          <p className="muted">
            Reusable standards shared across every project, searchable by the agents when
            generating a plan.
          </p>
        </div>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <>
          <section className="panel">
            <h2>Standards ({documents.length})</h2>
            {documents.length === 0 ? (
              <p>No standards uploaded yet. Upload a file or add text below.</p>
            ) : (
              <ul className="document-list">
                {documents.map((doc) => (
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
                          className="button-danger"
                          onClick={() => handleDelete(doc.document_id)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <h2>Upload standards</h2>
            <form className="form" onSubmit={handleUpload}>
              <FileUpload
                files={files}
                onFilesChange={setFiles}
                accept=".pdf,.docx,.txt,.md"
                title="Upload standards documents"
                hint="PDF, DOCX, TXT, or Markdown"
                disabled={uploading}
              />
              <div className="field">
                <label htmlFor="upload-type">Category</label>
                <input
                  id="upload-type"
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  placeholder="e.g. security, testing, estimation"
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
            <h2>Add standards text</h2>
            <form className="form" onSubmit={handleTextSubmit}>
              <div className="field">
                <label htmlFor="text-name">Document name</label>
                <input
                  id="text-name"
                  value={textName}
                  onChange={(e) => setTextName(e.target.value)}
                  placeholder="e.g. definition-of-done"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="text-type">Category</label>
                <input
                  id="text-type"
                  value={textType}
                  onChange={(e) => setTextType(e.target.value)}
                  placeholder="e.g. security, testing, estimation"
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
            <h2>Index standards</h2>
            <p className="muted">
              Standards must be indexed before agents can find them. "Index standards" only
              processes new files; use "Force re-index all" to rebuild everything from scratch.
            </p>
            <div className="form-actions">
              <button
                className="button"
                type="button"
                onClick={handleIndex}
                disabled={indexing || forceIndexing || documents.length === 0}
              >
                {indexing ? 'Indexing…' : 'Index standards'}
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
              <p className="muted">Upload at least one standards document first.</p>
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
        </>
      )}
    </div>
  )
}
