import { useId } from 'react'
import type { KeyboardEvent } from 'react'
import { ArrowRight } from 'lucide-react'

const MAX_CHARS = 500

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

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      if (!loading && value.trim()) onSubmit()
    }
  }

  return (
    <section className="panel p-4 shadow-[var(--shadow-card)] sm:p-5">
      <label htmlFor={id} className="text-meta">
        Question
      </label>
      <textarea
        id={id}
        value={value}
        maxLength={MAX_CHARS}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything... (e.g., What is the capital of India?)"
        rows={4}
        className="mt-2 w-full resize-none bg-transparent text-[16px] leading-7 text-ink placeholder:text-ink-muted/80 focus:outline-none disabled:opacity-60"
      />

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-xs text-ink-muted">
            {value.length}/{MAX_CHARS}
          </span>
          <span className="hidden text-xs text-ink-muted sm:inline">⌘/Ctrl + Enter</span>
        </div>

        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          aria-busy={loading}
          className="btn-primary w-full sm:w-auto"
        >
          {loading ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
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
