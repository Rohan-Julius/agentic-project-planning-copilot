/** A macOS-terminal-style visual for showing setup commands. Ported from a reference
 * "Terminal"/"TypingAnimation"/"AnimatedSpan" component's look — a titlebar with three
 * traffic-light dots, a dark card, monospace lines that reveal one after another, command
 * lines typed out character-by-character — without its `motion/react` (Framer Motion)
 * dependency, which this app doesn't take on for one static section (see PillNav.tsx for
 * the same substitution rationale). Sequencing is timing-based instead of the reference's
 * runtime "wait for the previous child to finish" state machine: each line's start time is
 * computed once from the lengths of the lines before it, then handed to plain CSS
 * `animation-delay` — no animation library needed for either the stagger or the typewriter
 * reveal (a monospace font's `ch` unit makes width-based steps() typing exact).
 *
 * All text stays real DOM text throughout (never hidden via aria-hidden or display:none),
 * so screen readers get the instructions immediately rather than only after the animation
 * plays — the animation is a decorative reveal, not the only way to access the content.
 */

export interface TerminalLine {
  /** Rendered with a "$ " prompt and typed out character-by-character. */
  command?: string
  /** Rendered as a plain reveal line (e.g. a "✔ ..." status line or trailing note). */
  text?: string
  tone?: 'success' | 'muted'
}

interface TerminalProps {
  label: string
  lines: TerminalLine[]
  className?: string
}

const MS_PER_CHAR = 28
const STATUS_DURATION_MS = 260
const LINE_GAP_MS = 140

export default function Terminal({ label, lines, className }: TerminalProps) {
  let elapsed = 0
  const timedLines = lines.map((line) => {
    const start = elapsed
    const duration = line.command ? line.command.length * MS_PER_CHAR : STATUS_DURATION_MS
    elapsed = start + duration + LINE_GAP_MS
    return { ...line, start }
  })

  return (
    <div className={`terminal${className ? ` ${className}` : ''}`} aria-label={label}>
      <div className="terminal-titlebar">
        <span className="terminal-dot terminal-dot-red" aria-hidden="true" />
        <span className="terminal-dot terminal-dot-yellow" aria-hidden="true" />
        <span className="terminal-dot terminal-dot-green" aria-hidden="true" />
      </div>
      <pre className="terminal-body">
        <code>
          {timedLines.map((line, i) =>
            line.command ? (
              <span
                key={i}
                className="terminal-line terminal-line-command"
                style={{ '--terminal-delay': `${line.start}ms` } as React.CSSProperties}
              >
                <span className="terminal-prompt">$</span>
                <span
                  className="terminal-typed"
                  style={
                    {
                      '--terminal-chars': line.command.length,
                      '--terminal-typing-duration': `${line.command.length * MS_PER_CHAR}ms`,
                      '--terminal-delay': `${line.start}ms`,
                    } as React.CSSProperties
                  }
                >
                  {line.command}
                </span>
              </span>
            ) : (
              <span
                key={i}
                className={`terminal-line terminal-line-${line.tone ?? 'success'}`}
                style={{ '--terminal-delay': `${line.start}ms` } as React.CSSProperties}
              >
                {line.text}
              </span>
            ),
          )}
        </code>
      </pre>
    </div>
  )
}
