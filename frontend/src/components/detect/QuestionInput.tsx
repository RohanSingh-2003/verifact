import { useEffect, useId, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { ArrowRight } from 'lucide-react'

interface QuestionInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  loading?: boolean
  disabled?: boolean
}

export function QuestionInput({
  value,
  onChange,
  onSubmit,
  loading = false,
  disabled = false,
}: QuestionInputProps) {
  const id = useId()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const canSubmit = !loading && !disabled && Boolean(value.trim())

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(el.scrollHeight, 320)
    el.style.height = `${Math.max(next, 112)}px`
  }, [value])

  function handleSubmit() {
    if (!canSubmit) return
    onSubmit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter') return
    if (event.shiftKey) return
    event.preventDefault()
    handleSubmit()
  }

  return (
    <section className="panel p-4 shadow-[var(--shadow-card)] sm:p-5">
      <label htmlFor={id} className="text-meta">
        Question
      </label>
      <textarea
        ref={textareaRef}
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything... (e.g., What is the capital of India?)"
        rows={4}
        className="mt-2 max-h-80 min-h-28 w-full resize-none overflow-y-auto bg-transparent text-[16px] leading-7 text-ink placeholder:text-ink-muted/80 focus:outline-none disabled:opacity-60"
      />

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          aria-busy={loading}
          className="btn-primary w-full sm:w-auto"
        >
          {loading ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-canvas/30 border-t-canvas" />
              Analyzing
            </>
          ) : (
            <>
              Analyze Answer
              <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
            </>
          )}
        </button>
      </div>
    </section>
  )
}
