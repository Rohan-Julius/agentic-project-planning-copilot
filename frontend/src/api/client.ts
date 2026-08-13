export const apiBaseUrl: string =
  (import.meta.env.VITE_apiBaseUrl as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function handleText(response: Response): Promise<string> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }
  return response.text()
}

export const api = {
  get: <T>(path: string) => fetch(`${apiBaseUrl}${path}`).then((r) => handle<T>(r)),

  // Export endpoints return the raw file body (JSON/Markdown/CSV text, not a JSON envelope) —
  // handle() always parses as JSON, so previewing those requires reading the response as text
  // instead (see ExportPreviewModal).
  getText: (path: string) => fetch(`${apiBaseUrl}${path}`).then((r) => handleText(r)),

  post: <T>(path: string, data: unknown) =>
    fetch(`${apiBaseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then((r) => handle<T>(r)),

  postForm: <T>(path: string, form: FormData) =>
    fetch(`${apiBaseUrl}${path}`, { method: 'POST', body: form }).then((r) => handle<T>(r)),

  delete: (path: string) =>
    fetch(`${apiBaseUrl}${path}`, { method: 'DELETE' }).then((r) => handle<void>(r)),
}
