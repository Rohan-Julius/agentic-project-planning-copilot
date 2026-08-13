import type { ReactNode } from 'react'
import { ArrowRight } from 'lucide-react'

/** Inner markup for `.button-hover` (see index.css) — drop inside either a `<button
 * className="button-hover">` or a react-router `<Link className="button-hover">`, since
 * the effect is pure CSS driven by the wrapping element's hover/focus state.
 */
export default function HoverButtonContent({ children }: { children: ReactNode }) {
  return (
    <>
      <span className="button-hover-base">
        <span className="button-hover-dot" aria-hidden="true" />
        <span>{children}</span>
      </span>
      <span className="button-hover-reveal" aria-hidden="true">
        <span>{children}</span>
        <ArrowRight className="button-hover-arrow" />
      </span>
    </>
  )
}
