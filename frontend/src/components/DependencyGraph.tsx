import { layoutDependencyGraph } from '../utils/dependencyGraphLayout'
import type { Dependency } from '../types'

interface DependencyGraphProps {
  dependencies: Dependency[]
  labelById: (id: string) => string
}

const COLUMN_WIDTH = 220
const ROW_HEIGHT = 72
const NODE_WIDTH = 180
const NODE_HEIGHT = 48
const PADDING = 24

const EDGE_STYLE: Record<Dependency['dependency_type'], string> = {
  BLOCKS: 'dependency-edge-blocks',
  REQUIRES: 'dependency-edge-requires',
  RELATES_TO: 'dependency-edge-relates',
}

/** Hand-rolled SVG layered-DAG view of the plan's Dependency list — deliberately not a new
 * npm graph library (see FileFormatCard.tsx's own comment on why this frontend stays off
 * component/graph libraries). Only items that appear in at least one dependency edge are
 * rendered; layout comes from `layoutDependencyGraph`. */
export default function DependencyGraph({ dependencies, labelById }: DependencyGraphProps) {
  if (dependencies.length === 0) {
    return <p className="muted">No dependencies to graph.</p>
  }

  const layout = layoutDependencyGraph(dependencies, labelById)
  const maxRank = Math.max(...layout.nodes.map((n) => n.rank))
  const maxOrder = Math.max(...layout.nodes.map((n) => n.order))
  const width = PADDING * 2 + (maxRank + 1) * COLUMN_WIDTH
  const height = PADDING * 2 + (maxOrder + 1) * ROW_HEIGHT

  const centerOf = (node: { rank: number; order: number }) => ({
    x: PADDING + node.rank * COLUMN_WIDTH + NODE_WIDTH / 2,
    y: PADDING + node.order * ROW_HEIGHT + NODE_HEIGHT / 2,
  })
  const nodeById = Object.fromEntries(layout.nodes.map((n) => [n.id, n]))

  return (
    <div className="dependency-graph-wrap">
      {layout.cyclic && (
        <p className="error">
          A dependency cycle was detected — the layout below may not reflect a valid order.
        </p>
      )}
      <svg
        className="dependency-graph-svg"
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="img"
        aria-label="Dependency graph"
      >
        <defs>
          <marker
            id="dependency-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" className="dependency-arrowhead" />
          </marker>
        </defs>
        {layout.edges.map((edge) => {
          const from = nodeById[edge.from]
          const to = nodeById[edge.to]
          if (!from || !to) return null
          const a = centerOf(from)
          const b = centerOf(to)
          return (
            <line
              key={edge.id}
              x1={a.x + NODE_WIDTH / 2}
              y1={a.y}
              x2={b.x - NODE_WIDTH / 2}
              y2={b.y}
              className={`dependency-edge ${EDGE_STYLE[edge.dependencyType]}`}
              markerEnd="url(#dependency-arrow)"
            />
          )
        })}
        {layout.nodes.map((node) => {
          const c = centerOf(node)
          return (
            <g key={node.id} transform={`translate(${c.x - NODE_WIDTH / 2}, ${c.y - NODE_HEIGHT / 2})`}>
              <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx={8} className="dependency-node-rect" />
              <text x={NODE_WIDTH / 2} y={NODE_HEIGHT / 2} className="dependency-node-text">
                {node.label.length > 26 ? `${node.label.slice(0, 25)}…` : node.label}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="muted dependency-graph-legend">
        <span className="dependency-legend-swatch dependency-edge-blocks" /> Blocks{' '}
        <span className="dependency-legend-swatch dependency-edge-requires" /> Requires{' '}
        <span className="dependency-legend-swatch dependency-edge-relates" /> Relates to
      </p>
    </div>
  )
}
