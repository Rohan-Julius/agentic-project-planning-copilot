export type ExportFormat = 'json' | 'markdown' | 'csv' | 'zip' | 'docx'

interface FileFormatCardProps {
  format: ExportFormat
  /** Visible label, e.g. "Markdown" or "ZIP (all formats + reviewer report)". */
  label: string
  /** Renders a <button> — use for formats with a preview (see ExportPreviewModal). */
  onClick?: () => void
  /** Renders an <a> instead of a <button> — use for formats that only download (e.g. zip,
   * which is a binary bundle with nothing sensible to preview as text). */
  href?: string
}

const FORMAT_BADGE: Record<ExportFormat, string> = {
  json: 'JSON',
  markdown: 'MD',
  csv: 'CSV',
  zip: 'ZIP',
  docx: 'DOCX',
}

/** A small file-icon tile — colored format badge over a "paper" card with a placeholder
 * glyph hinting at the format's shape (braces for JSON, a heading for Markdown, a grid for
 * CSV, dots for a zip's file listing). Visual language ported from a reference "FileCard"
 * component, not its implementation — the reference is a Tailwind/shadcn component and this
 * codebase deliberately doesn't take on Tailwind or shadcn (see CLAUDE.md), so this rebuilds
 * the same look with plain CSS classes and this app's own design tokens instead. The format
 * badge colors are the one deliberate exception to using theme tokens: like the reference,
 * they're meant to be a fixed, recognizable format identity (JSON is always amber, etc.),
 * not something that should shift with the light/dark toggle. */
export default function FileFormatCard({ format, label, onClick, href }: FileFormatCardProps) {
  const content = (
    <>
      <span className="file-format-card-inner">
        <span className={`file-format-badge file-format-badge-${format}`}>
          {FORMAT_BADGE[format]}
        </span>
        <span className="file-format-sheet">
          <FormatGlyph format={format} />
        </span>
      </span>
      <span className="file-format-label">{label}</span>
    </>
  )

  if (href) {
    return (
      <a className="file-format-card" href={href}>
        {content}
      </a>
    )
  }

  return (
    <button type="button" className="file-format-card" onClick={onClick}>
      {content}
    </button>
  )
}

function FormatGlyph({ format }: { format: ExportFormat }) {
  if (format === 'json') {
    return (
      <span className="file-format-lines" aria-hidden="true">
        <span className="file-format-brace">{'{'}</span>
        <span className="file-format-line file-format-line-w2" />
        <span className="file-format-line file-format-line-w3" />
        <span className="file-format-brace">{'}'}</span>
      </span>
    )
  }
  if (format === 'markdown') {
    return (
      <span className="file-format-lines" aria-hidden="true">
        <span className="file-format-heading" />
        <span className="file-format-line file-format-line-w3" />
        <span className="file-format-line file-format-line-w2" />
        <span className="file-format-line file-format-line-w3" />
      </span>
    )
  }
  if (format === 'csv') {
    return (
      <span className="file-format-grid" aria-hidden="true">
        {Array.from({ length: 9 }).map((_, i) => (
          <span key={i} className="file-format-cell" />
        ))}
      </span>
    )
  }
  if (format === 'docx') {
    return (
      <span className="file-format-lines" aria-hidden="true">
        <span className="file-format-heading" />
        <span className="file-format-line file-format-line-w3" />
        <span className="file-format-line file-format-line-w2" />
        <span className="file-format-line file-format-line-w3" />
        <span className="file-format-line file-format-line-w2" />
      </span>
    )
  }
  return (
    <span className="file-format-dots" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <span key={i} className="file-format-dot" style={{ opacity: i % 2 === 0 ? 1 : 0.35 }} />
      ))}
    </span>
  )
}
