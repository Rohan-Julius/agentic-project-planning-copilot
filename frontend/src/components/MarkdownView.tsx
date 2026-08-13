import { parseInline, parseMarkdown, type InlineToken, type MarkdownBlock } from '../utils/markdown'

/** Renders an export's Markdown as an actual formatted document — headings, bold, lists,
 * and the traceability table — instead of a raw text dump, the way a desktop file preview
 * (Finder Quick Look, VS Code's Markdown preview, ...) would show a .md file. See
 * utils/markdown.ts for why this is a small hand-rolled parser rather than a library. */
export default function MarkdownView({ source }: { source: string }) {
  const blocks = parseMarkdown(source)
  return <div className="markdown-view">{blocks.map((block, i) => renderBlock(block, i))}</div>
}

function renderBlock(block: MarkdownBlock, key: number) {
  switch (block.type) {
    case 'heading': {
      const Tag = `h${block.level}` as 'h1' | 'h2' | 'h3'
      return <Tag key={key}>{renderInline(block.text)}</Tag>
    }
    case 'paragraph':
      return <p key={key}>{renderInline(block.text)}</p>
    case 'list':
      return (
        <ul key={key} className="markdown-list">
          {block.items.map((item, i) => (
            <li key={i} style={{ marginLeft: item.indent * 16 }}>
              {renderInline(item.text)}
            </li>
          ))}
        </ul>
      )
    case 'table':
      return (
        <div key={key} className="markdown-table-wrap">
          <table className="markdown-table">
            <thead>
              <tr>
                {block.headers.map((header, i) => (
                  <th key={i}>{renderInline(header)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c}>{renderInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    default:
      return null
  }
}

function renderInline(text: string) {
  return parseInline(text).map((token, i) => renderToken(token, i))
}

function renderToken(token: InlineToken, key: number) {
  if (token.type === 'bold') return <strong key={key}>{token.value}</strong>
  if (token.type === 'code') return <code key={key}>{token.value}</code>
  return token.value
}
