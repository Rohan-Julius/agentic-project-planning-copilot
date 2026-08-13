import { describe, expect, it } from 'vitest'
import { columnLetter, parseCsv } from './csv'

describe('parseCsv', () => {
  it('splits a simple header + row', () => {
    expect(parseCsv('a,b,c\n1,2,3')).toEqual([
      ['a', 'b', 'c'],
      ['1', '2', '3'],
    ])
  })

  it('keeps commas inside quoted fields as part of the field', () => {
    expect(parseCsv('Summary,Description\n"Leave request","Employees, and managers"')).toEqual([
      ['Summary', 'Description'],
      ['Leave request', 'Employees, and managers'],
    ])
  })

  it('unescapes doubled quotes inside a quoted field', () => {
    expect(parseCsv('Note\n"She said ""go"" today"')).toEqual([['Note'], ['She said "go" today']])
  })

  it('keeps embedded newlines inside a quoted field as part of the field', () => {
    expect(parseCsv('Note\n"line one\nline two"')).toEqual([['Note'], ['line one\nline two']])
  })

  it('handles a trailing row with no final newline', () => {
    expect(parseCsv('a,b\n1,2')).toEqual([
      ['a', 'b'],
      ['1', '2'],
    ])
  })

  it('normalizes CRLF line endings', () => {
    expect(parseCsv('a,b\r\n1,2\r\n')).toEqual([
      ['a', 'b'],
      ['1', '2'],
    ])
  })

  it('parses the real header shape produced by build_jira_csv_text', () => {
    const header =
      'Issue Type,Summary,Description,Epic Name,Epic Link,Parent ID,Priority,Story Points,' +
      'Acceptance Criteria,Dependencies,Labels,Source References,AI Classification'
    expect(parseCsv(header)[0]).toEqual([
      'Issue Type',
      'Summary',
      'Description',
      'Epic Name',
      'Epic Link',
      'Parent ID',
      'Priority',
      'Story Points',
      'Acceptance Criteria',
      'Dependencies',
      'Labels',
      'Source References',
      'AI Classification',
    ])
  })
})

describe('columnLetter', () => {
  it('labels the first 26 columns A through Z', () => {
    expect(columnLetter(0)).toBe('A')
    expect(columnLetter(12)).toBe('M')
    expect(columnLetter(25)).toBe('Z')
  })

  it('continues into double letters past Z', () => {
    expect(columnLetter(26)).toBe('AA')
    expect(columnLetter(27)).toBe('AB')
    expect(columnLetter(51)).toBe('AZ')
    expect(columnLetter(52)).toBe('BA')
  })
})
