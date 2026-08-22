import { describe, expect, it } from 'vitest'
import { diffById } from './versionDiff'

interface Item {
  id: string
  title: string
}

describe('diffById', () => {
  it('categorizes added, removed, modified, and unchanged items', () => {
    const previous: Item[] = [
      { id: 'A', title: 'Alpha' },
      { id: 'B', title: 'Beta' },
      { id: 'C', title: 'Gamma' },
    ]
    const next: Item[] = [
      { id: 'A', title: 'Alpha' },
      { id: 'B', title: 'Beta v2' },
      { id: 'D', title: 'Delta' },
    ]

    const result = diffById(previous, next, (item) => item.id)

    expect(result.added.map((i) => i.id)).toEqual(['D'])
    expect(result.removed.map((i) => i.id)).toEqual(['C'])
    expect(result.modified.map((m) => m.next.id)).toEqual(['B'])
    expect(result.unchanged.map((i) => i.id)).toEqual(['A'])
  })

  it('returns everything as added when previous is empty', () => {
    const result = diffById<Item, string>([], [{ id: 'A', title: 'Alpha' }], (i) => i.id)
    expect(result.added).toHaveLength(1)
    expect(result.removed).toHaveLength(0)
  })
})
