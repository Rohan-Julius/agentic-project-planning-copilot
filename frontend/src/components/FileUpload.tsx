import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { File as FileIcon, UploadCloud, X } from 'lucide-react'

interface FileUploadProps {
  /** Controlled by the parent so it can clear the list after a successful submit. */
  files: File[]
  onFilesChange: (files: File[]) => void
  /** Passed straight through to the native file input's `accept` attribute. */
  accept?: string
  /** Card heading, e.g. "Upload your files". */
  title?: string
  /** Card subtitle beneath the title — accepted formats/size, e.g. "PDF, DOCX, TXT, or Markdown". */
  hint?: string
  disabled?: boolean
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

/** Drag-and-drop / browse multi-file picker with a removable file list. Purely a picker —
 * it doesn't upload anything itself; the parent owns `files` and decides what to do with
 * them (see DocumentWorkspace's `handleUpload`).
 */
export default function FileUpload({
  files,
  onFilesChange,
  accept,
  title = 'Upload your files',
  hint = 'PDF, DOCX, TXT, or Markdown',
  disabled = false,
}: FileUploadProps) {
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function addFiles(newFiles: FileList | null) {
    if (!newFiles || newFiles.length === 0) return
    onFilesChange([...files, ...Array.from(newFiles)])
  }

  function handleDrag(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (disabled) return
    if (event.type === 'dragenter' || event.type === 'dragover') setDragActive(true)
    else if (event.type === 'dragleave') setDragActive(false)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    event.stopPropagation()
    setDragActive(false)
    if (disabled) return
    addFiles(event.dataTransfer.files)
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(event.target.files)
    // Reset so re-selecting the same file after removing it still fires onChange.
    event.target.value = ''
  }

  function removeFile(indexToRemove: number) {
    onFilesChange(files.filter((_, index) => index !== indexToRemove))
  }

  return (
    <div className="file-upload">
      <div className="file-upload-card-header">
        <h3 className="file-upload-card-title">{title}</h3>
        <p className="file-upload-card-subtitle">{hint}</p>
      </div>

      <div
        className={`file-upload-dropzone${dragActive ? ' is-active' : ''}${disabled ? ' is-disabled' : ''}`}
        onClick={() => !disabled && inputRef.current?.click()}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload documents"
        onKeyDown={(event) => {
          if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault()
            inputRef.current?.click()
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          onChange={handleChange}
          disabled={disabled}
          className="file-upload-input"
        />
        <UploadCloud className="file-upload-icon" aria-hidden="true" />
        <p className="file-upload-copy">
          Drag &amp; drop files or <span className="file-upload-browse">Browse</span>
        </p>
      </div>

      {files.length > 0 && (
        <ul className="file-upload-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="file-upload-item">
              <div className="file-upload-item-info">
                <span className="file-upload-item-icon" aria-hidden="true">
                  <FileIcon className="file-upload-item-icon-svg" />
                </span>
                <span className="file-upload-item-text">
                  <span className="file-upload-item-name">{file.name}</span>
                  <span className="file-upload-item-size">{formatSize(file.size)}</span>
                </span>
              </div>
              <button
                type="button"
                className="file-upload-remove"
                onClick={() => removeFile(index)}
                aria-label={`Remove ${file.name}`}
              >
                <X className="file-upload-remove-svg" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
