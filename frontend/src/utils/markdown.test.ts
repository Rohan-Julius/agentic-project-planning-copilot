import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from './markdown'

describe('parseInline', () => {
  it('returns a single text token for plain text', () => {
    expect(parseInline('plain text')).toEqual([{ type: 'text', value: 'plain text' }])
  })

  it('extracts bold spans', () => {
    expect(parseInline('**Status:** APPROVED')).toEqual([
      { type: 'bold', value: 'Status:' },
      { type: 'text', value: ' APPROVED' },
    ])
  })

  it('extracts inline code spans', () => {
    expect(parseInline('EPIC-1 `[SOURCE_BACKED]`')).toEqual([
      { type: 'text', value: 'EPIC-1 ' },
      { type: 'code', value: '[SOURCE_BACKED]' },
    ])
  })

  it('handles bold and code in the same line', () => {
    expect(parseInline('**Priority:** high `[note]`')).toEqual([
      { type: 'bold', value: 'Priority:' },
      { type: 'text', value: ' high ' },
      { type: 'code', value: '[note]' },
    ])
  })
})

describe('parseMarkdown', () => {
  it('parses headings at each level', () => {
    expect(parseMarkdown('# Title\n## Section\n### Sub')).toEqual([
      { type: 'heading', level: 1, text: 'Title' },
      { type: 'heading', level: 2, text: 'Section' },
      { type: 'heading', level: 3, text: 'Sub' },
    ])
  })

  it('parses a flat bullet list', () => {
    expect(parseMarkdown('- first\n- second')).toEqual([
      {
        type: 'list',
        items: [
          { text: 'first', indent: 0 },
          { text: 'second', indent: 0 },
        ],
      },
    ])
  })

  it('tracks indent level for nested acceptance-criteria bullets', () => {
    const source = '- **Acceptance criteria:**\n  - AC1: Given a When b Then c'
    expect(parseMarkdown(source)).toEqual([
      {
        type: 'list',
        items: [
          { text: '**Acceptance criteria:**', indent: 0 },
          { text: 'AC1: Given a When b Then c', indent: 1 },
        ],
      },
    ])
  })

  it('parses a GFM-style table with a header separator row', () => {
    const source = [
      '| Requirement | Source | Epic |',
      '|---|---|---|',
      '| REQ-1 | doc.pdf p.2 | EPIC-1 |',
    ].join('\n')
    expect(parseMarkdown(source)).toEqual([
      {
        type: 'table',
        headers: ['Requirement', 'Source', 'Epic'],
        rows: [['REQ-1', 'doc.pdf p.2', 'EPIC-1']],
      },
    ])
  })

  it('collapses consecutive plain lines into one paragraph', () => {
    expect(parseMarkdown('As a user, I want x,\nso that y.')).toEqual([
      { type: 'paragraph', text: 'As a user, I want x, so that y.' },
    ])
  })

  it('parses the real shape produced by build_markdown_export', () => {
    const source = [
      '# Project Plan (AI-Generated Draft)',
      '',
      '**Status:** APPROVED',
      '',
      '## 3. Epics',
      '### EPIC-1: Leave requests `[SOURCE_BACKED]`',
      '- **Objective:** Let employees request leave.',
      '- **Priority:** high',
      '',
      '## 8. Traceability Matrix',
      '| Requirement | Source | Epic | Story | Acceptance Criteria |',
      '|---|---|---|---|---|',
      '| REQ-1 | doc.pdf p.2 | EPIC-1 |  | AC1 |',
    ].join('\n')

    expect(parseMarkdown(source)).toEqual([
      { type: 'heading', level: 1, text: 'Project Plan (AI-Generated Draft)' },
      { type: 'paragraph', text: '**Status:** APPROVED' },
      { type: 'heading', level: 2, text: '3. Epics' },
      { type: 'heading', level: 3, text: 'EPIC-1: Leave requests `[SOURCE_BACKED]`' },
      {
        type: 'list',
        items: [
          { text: '**Objective:** Let employees request leave.', indent: 0 },
          { text: '**Priority:** high', indent: 0 },
        ],
      },
      { type: 'heading', level: 2, text: '8. Traceability Matrix' },
      {
        type: 'table',
        headers: ['Requirement', 'Source', 'Epic', 'Story', 'Acceptance Criteria'],
        rows: [['REQ-1', 'doc.pdf p.2', 'EPIC-1', '', 'AC1']],
      },
    ])
  })
})
