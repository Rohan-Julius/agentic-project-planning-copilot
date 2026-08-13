import { useEffect, useRef, useState } from 'react'
import { api, apiBaseUrl, ApiError } from '../api/client'
import type { ExportFormat } from './FileFormatCard'
import MarkdownView from './MarkdownView'
import SpreadsheetView from './SpreadsheetView'

export interface ExportPreviewTarget {
  /** Only text-based formats get a preview — zip is a binary bundle (see FileFormatCard). */
  format: Exclude<ExportFormat, 'zip'>
  label: string
  /** API path, e.g. `/projects/{id}/export/json`. */
  path: string
  filename: string
}

interface ExportPreviewModalProps {
  target: ExportPreviewTarget | null
  onClose: () => void
}

/** Built on the native <dialog> element rather than a hand-rolled overlay — it gets focus
 * trapping, Escape-to-close, and backdrop rendering for free, which keeps this dependency-free
 * (see FileFormatCard.tsx for why this app doesn't reach for a component library here). */
export default function ExportPreviewModal({ target, onClose }: ExportPreviewModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (target && !dialog.open) {
      dialog.showModal()
    } else if (!target && dialog.open) {
      dialog.close()
    }
  }, [target])

  useEffect(() => {
    if (!target) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setContent('')
    api
      .getText(target.path)
      .then((text) => {
        if (cancelled) return
        setContent(target.format === 'json' ? prettyPrintJson(text) : text)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : (err as Error).message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [target])

  function handleBackdropClick(event: React.MouseEvent<HTMLDialogElement>) {
    // A click that lands on the <dialog> element itself (not one of its children) means it
    // landed on the ::backdrop area — the visible card fills the rest via child elements.
    if (event.target === dialogRef.current) onClose()
  }

  return (
    <dialog
      ref={dialogRef}
      className="export-preview-dialog"
      onClose={onClose}
      onCancel={onClose}
      onClick={handleBackdropClick}
    >
      {target && (
        <div className="export-preview">
          <header className="export-preview-header">
            <span
              className={`file-format-badge file-format-badge-${target.format} export-preview-badge`}
            >
              {target.format.toUpperCase()}
            </span>
            <h2>{target.label}</h2>
            <button
              type="button"
              className="export-preview-close"
              onClick={onClose}
              aria-label="Close preview"
            >
              ×
            </button>
          </header>

          <div className="export-preview-body">
            {loading && <p className="muted">Loading preview…</p>}
            {error && <p className="error">{error}</p>}
            {!loading && !error && <PreviewContent format={target.format} content={content} />}
          </div>

          <footer className="export-preview-footer">
            <a className="button" href={`${apiBaseUrl}${target.path}`} download={target.filename}>
              Download {target.label}
            </a>
          </footer>
        </div>
      )}
    </dialog>
  )
}

// Each format gets the kind of preview a desktop file viewer would give it: Markdown renders
// as an actual formatted document, CSV as an actual spreadsheet grid, JSON as pretty-printed
// text (already reads like a code/JSON viewer, unlike a raw single-line comma dump).
function PreviewContent({ format, content }: { format: ExportPreviewTarget['format']; content: string }) {
  if (format === 'markdown') return <MarkdownView source={content} />
  if (format === 'csv') return <SpreadsheetView source={content} />
  return <pre className="export-preview-content">{content}</pre>
}

function prettyPrintJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}
