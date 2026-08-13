/**
 * A minimal Markdown parser scoped to exactly what
 * app/services/export_service.py::build_markdown_export actually emits — headings (#/##/###),
 * bold (**text**), inline code (`text`), bullet lists (including one level of 2-space-indented
 * nesting, used for acceptance criteria under each story), and one GFM-style table (the
 * traceability matrix). Not a general-purpose Markdown implementation.
 *
 * Deliberately hand-rolled instead of pulling in a library: the output only ever needs to
 * become React children (see components/MarkdownView.tsx), so text stays real text through
 * React's own escaping the whole way — no dangerouslySetInnerHTML, no separate sanitizer
 * dependency to keep that safe.
 */

export type InlineToken =
  | { type: 'text'; value: string }
  | { type: 'bold'; value: string }
  | { type: 'code'; value: string }

const INLINE_PATTERN = /\*\*(.+?)\*\*|`([^`]+)`/g

export function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  let lastIndex = 0
  for (const match of text.matchAll(INLINE_PATTERN)) {
    const index = match.index ?? 0
    if (index > lastIndex) {
      tokens.push({ type: 'text', value: text.slice(lastIndex, index) })
    }
    if (match[1] !== undefined) {
      tokens.push({ type: 'bold', value: match[1] })
    } else {
      tokens.push({ type: 'code', value: match[2] })
    }
    lastIndex = index + match[0].length
  }
  if (lastIndex < text.length) {
    tokens.push({ type: 'text', value: text.slice(lastIndex) })
  }
  return tokens
}

export type MarkdownBlock =
  | { type: 'heading'; level: 1 | 2 | 3; text: string }
  | { type: 'list'; items: { text: string; indent: number }[] }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'paragraph'; text: string }

const HEADING_RE = /^(#{1,3})\s+(.*)$/
const LIST_ITEM_RE = /^(\s*)-\s+(.*)$/
const TABLE_SEPARATOR_RE = /^\s*\|[\s:|-]+\|\s*$/

export function parseMarkdown(source: string): MarkdownBlock[] {
  const lines = source.split('\n')
  const blocks: MarkdownBlock[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      i++
      continue
    }

    const headingMatch = HEADING_RE.exec(line)
    if (headingMatch) {
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length as 1 | 2 | 3,
        text: headingMatch[2].trim(),
      })
      i++
      continue
    }

    if (line.trim().startsWith('|') && TABLE_SEPARATOR_RE.test(lines[i + 1] ?? '')) {
      const headers = splitTableRow(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitTableRow(lines[i]))
        i++
      }
      blocks.push({ type: 'table', headers, rows })
      continue
    }

    if (LIST_ITEM_RE.test(line)) {
      const items: { text: string; indent: number }[] = []
      while (i < lines.length) {
        const match = LIST_ITEM_RE.exec(lines[i])
        if (!match) break
        items.push({ indent: Math.floor(match[1].length / 2), text: match[2].trim() })
        i++
      }
      blocks.push({ type: 'list', items })
      continue
    }

    const paragraphLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !HEADING_RE.test(lines[i]) &&
      !LIST_ITEM_RE.test(lines[i]) &&
      !lines[i].trim().startsWith('|')
    ) {
      paragraphLines.push(lines[i].trim())
      i++
    }
    if (paragraphLines.length > 0) {
      blocks.push({ type: 'paragraph', text: paragraphLines.join(' ') })
    } else {
      i++
    }
  }

  return blocks
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}
