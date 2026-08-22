/** Generic by-ID diff (§32 'version comparison' stretch goal): given two lists of the same
 * artifact type from two plan versions, categorize each item as added (in `next` only),
 * removed (in `prev` only), or modified (present in both, but not deeply equal — a
 * JSON-stringify comparison, not a field-level diff; a real field-level diff is a larger,
 * separate improvement, not silently promised here).
 */
export interface ArtifactDiff<T> {
  added: T[]
  removed: T[]
  modified: { previous: T; next: T }[]
  unchanged: T[]
}

export function diffById<T, K extends string>(
  previous: T[],
  next: T[],
  idKey: (item: T) => K,
): ArtifactDiff<T> {
  const prevById = new Map(previous.map((item) => [idKey(item), item]))
  const nextById = new Map(next.map((item) => [idKey(item), item]))

  const added: T[] = []
  const modified: { previous: T; next: T }[] = []
  const unchanged: T[] = []

  for (const [id, nextItem] of nextById) {
    const prevItem = prevById.get(id)
    if (prevItem === undefined) {
      added.push(nextItem)
    } else if (JSON.stringify(prevItem) !== JSON.stringify(nextItem)) {
      modified.push({ previous: prevItem, next: nextItem })
    } else {
      unchanged.push(nextItem)
    }
  }

  const removed = previous.filter((item) => !nextById.has(idKey(item)))

  return { added, removed, modified, unchanged }
}
