/** Turns a flat list of plan Dependencies into a layered-DAG layout: every node's `rank` is
 * its longest path from a root (a node with no incoming edge), computed via Kahn's algorithm
 * so ties resolve deterministically. `order` is the node's position within its rank, assigned
 * in first-seen order. Only items that appear in at least one dependency edge are included —
 * this renders the dependency structure, not the whole backlog.
 *
 * A dependency cycle (which a real plan should never produce, but an LLM-authored one is not
 * guaranteed to avoid) would make "longest path from a root" undefined for the nodes in it.
 * Rather than loop forever or throw, any node still unranked after all in-degree-0 nodes are
 * exhausted is dropped into rank 0 and the whole layout is flagged `cyclic: true` so the UI can
 * show a warning instead of silently rendering a subtly wrong graph.
 */
export interface GraphNode {
  id: string
  label: string
  rank: number
  order: number
}

export interface GraphEdge {
  id: string
  from: string
  to: string
  dependencyType: 'BLOCKS' | 'REQUIRES' | 'RELATES_TO'
}

export interface GraphLayout {
  nodes: GraphNode[]
  edges: GraphEdge[]
  cyclic: boolean
}

interface DependencyLike {
  dependency_id: string
  blocking_item_id: string
  blocked_item_id: string
  dependency_type: 'BLOCKS' | 'REQUIRES' | 'RELATES_TO'
}

export function layoutDependencyGraph(
  dependencies: DependencyLike[],
  labelById: (id: string) => string,
): GraphLayout {
  const nodeIds: string[] = []
  const seen = new Set<string>()
  for (const dep of dependencies) {
    if (!seen.has(dep.blocking_item_id)) {
      seen.add(dep.blocking_item_id)
      nodeIds.push(dep.blocking_item_id)
    }
    if (!seen.has(dep.blocked_item_id)) {
      seen.add(dep.blocked_item_id)
      nodeIds.push(dep.blocked_item_id)
    }
  }

  const outgoing = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  for (const id of nodeIds) {
    outgoing.set(id, [])
    inDegree.set(id, 0)
  }
  for (const dep of dependencies) {
    outgoing.get(dep.blocking_item_id)!.push(dep.blocked_item_id)
    inDegree.set(dep.blocked_item_id, (inDegree.get(dep.blocked_item_id) ?? 0) + 1)
  }

  const rank = new Map<string, number>()
  let frontier = nodeIds.filter((id) => inDegree.get(id) === 0)
  const remainingInDegree = new Map(inDegree)
  let currentRank = 0
  const visited = new Set<string>()
  while (frontier.length > 0) {
    for (const id of frontier) {
      rank.set(id, currentRank)
      visited.add(id)
    }
    const next: string[] = []
    for (const id of frontier) {
      for (const target of outgoing.get(id) ?? []) {
        const remaining = (remainingInDegree.get(target) ?? 0) - 1
        remainingInDegree.set(target, remaining)
        if (remaining === 0 && !visited.has(target)) {
          next.push(target)
        }
      }
    }
    frontier = next
    currentRank += 1
  }

  const cyclic = visited.size < nodeIds.length
  for (const id of nodeIds) {
    if (!rank.has(id)) rank.set(id, 0)
  }

  const orderCounters = new Map<number, number>()
  const nodes: GraphNode[] = nodeIds.map((id) => {
    const r = rank.get(id)!
    const order = orderCounters.get(r) ?? 0
    orderCounters.set(r, order + 1)
    return { id, label: labelById(id), rank: r, order }
  })

  const edges: GraphEdge[] = dependencies.map((dep) => ({
    id: dep.dependency_id,
    from: dep.blocking_item_id,
    to: dep.blocked_item_id,
    dependencyType: dep.dependency_type,
  }))

  return { nodes, edges, cyclic }
}
