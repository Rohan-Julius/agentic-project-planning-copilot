import type { ButtonHTMLAttributes } from 'react'

/** The "gives results" button (see index.css `.button-shiny`) — reserved for the moment
 * an action actually makes the AI pipeline produce something. Deliberately not reused for
 * routine actions; the effect only reads as meaningful if it stays rare.
 */
export default function ShinyButton({
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`button-shiny ${className}`.trim()} {...props}>
      <span>{children}</span>
    </button>
  )
}
