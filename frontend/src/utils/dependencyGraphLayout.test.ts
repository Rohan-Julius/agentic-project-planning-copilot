import { describe, expect, it } from 'vitest'
import { layoutDependencyGraph } from './dependencyGraphLayout'

const label = (id: string) => `Label(${id})`

describe('layoutDependencyGraph', () => {
  it('places a simple chain A -> B -> C into increasing ranks', () => {
    const deps = [
      { dependency_id: 'D-1', blocking_item_id: 'A', blocked_item_id: 'B', dependency_type: 'BLOCKS' as const },
      { dependency_id: 'D-2', blocking_item_id: 'B', blocked_item_id: 'C', dependency_type: 'BLOCKS' as const },
    ]
    const layout = layoutDependencyGraph(deps, label)
    const byId = Object.fromEntries(layout.nodes.map((n) => [n.id, n]))
    expect(byId.A.rank).toBe(0)
    expect(byId.B.rank).toBe(1)
    expect(byId.C.rank).toBe(2)
    expect(layout.edges).toHaveLength(2)
    expect(layout.cyclic).toBe(false)
  })

  it('gives nodes with no dependencies at all no representation (graph is dependency-only)', () => {
    const layout = layoutDependencyGraph([], label)
    expect(layout.nodes).toHaveLength(0)
    expect(layout.edges).toHaveLength(0)
  })

  it('handles a diamond (A -> B, A -> C, B -> D, C -> D) without duplicating D', () => {
    const deps = [
      { dependency_id: 'D-1', blocking_item_id: 'A', blocked_item_id: 'B', dependency_type: 'BLOCKS' as const },
      { dependency_id: 'D-2', blocking_item_id: 'A', blocked_item_id: 'C', dependency_type: 'BLOCKS' as const },
      { dependency_id: 'D-3', blocking_item_id: 'B', blocked_item_id: 'D', dependency_type: 'REQUIRES' as const },
      { dependency_id: 'D-4', blocking_item_id: 'C', blocked_item_id: 'D', dependency_type: 'REQUIRES' as const },
    ]
    const layout = layoutDependencyGraph(deps, label)
    expect(layout.nodes).toHaveLength(4)
    const byId = Object.fromEntries(layout.nodes.map((n) => [n.id, n]))
    expect(byId.A.rank).toBe(0)
    expect(byId.D.rank).toBe(2)
    expect(layout.cyclic).toBe(false)
  })

  it('detects a cycle and still returns a layout instead of hanging', () => {
    const deps = [
      { dependency_id: 'D-1', blocking_item_id: 'A', blocked_item_id: 'B', dependency_type: 'BLOCKS' as const },
      { dependency_id: 'D-2', blocking_item_id: 'B', blocked_item_id: 'A', dependency_type: 'BLOCKS' as const },
    ]
    const layout = layoutDependencyGraph(deps, label)
    expect(layout.cyclic).toBe(true)
    expect(layout.nodes).toHaveLength(2)
    expect(layout.edges).toHaveLength(2)
  })

  it('uses labelById to set node labels', () => {
    const deps = [
      { dependency_id: 'D-1', blocking_item_id: 'A', blocked_item_id: 'B', dependency_type: 'BLOCKS' as const },
    ]
    const layout = layoutDependencyGraph(deps, label)
    const a = layout.nodes.find((n) => n.id === 'A')!
    expect(a.label).toBe('Label(A)')
  })
})
