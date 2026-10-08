import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { AnswerModelOption } from '../../types'

interface AnswerModelSelectorProps {
  models: AnswerModelOption[]
  selectedId: string
  onSelect: (modelId: string) => void
  disabled?: boolean
}

export function AnswerModelSelector({
  models,
  selectedId,
  onSelect,
  disabled = false,
}: AnswerModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedModel = models.find((m) => m.id === selectedId) ?? models[0] ?? {
    id: 'gemma',
    name: 'Gemma 4:26B',
    provider: 'ollama',
    providerDisplay: 'Ollama Cloud',
    configured: true,
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-meta">Answer Model</label>
        <span className="text-[11px] text-ink-muted">Independent verifiers assigned dynamically</span>
      </div>

      <button
        type="button"
        id="answer-model-selector-button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 rounded-[var(--radius-sm)] border border-line bg-surface px-3.5 py-2.5 text-left transition-colors hover:border-line-strong focus:outline-none focus:ring-1 focus:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="truncate text-sm font-medium text-ink">
            {selectedModel.name}
          </span>
          <span className="shrink-0 text-xs text-ink-muted">
            {selectedModel.providerDisplay}
          </span>
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-ink-muted transition-transform duration-150 ${
            isOpen ? 'rotate-180' : ''
          }`}
          strokeWidth={2}
        />
      </button>

      {isOpen && (
        <ul
          role="listbox"
          aria-label="Available Answer Models"
          className="absolute z-30 mt-1.5 max-h-80 w-full overflow-y-auto rounded-[var(--radius-sm)] border border-line bg-surface p-1 shadow-[var(--shadow-float)] focus:outline-none"
        >
          {models.map((model) => {
            const isSelected = model.id === selectedModel.id
            const isAvailable = model.configured

            return (
              <li
                key={model.id}
                role="option"
                aria-selected={isSelected}
                aria-disabled={!isAvailable}
                onClick={() => {
                  if (!isAvailable || disabled) return
                  onSelect(model.id)
                  setIsOpen(false)
                }}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-xs transition-colors ${
                  !isAvailable
                    ? 'cursor-not-allowed opacity-50'
                    : isSelected
                      ? 'bg-surface-muted text-ink'
                      : 'text-ink hover:bg-surface-muted/60'
                }`}
              >
                <div className="flex min-w-0 flex-col">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink">{model.name}</span>
                    {isSelected && (
                      <Check className="h-3.5 w-3.5 text-accent" strokeWidth={2.5} />
                    )}
                  </div>
                  <span className="text-[11px] text-ink-muted">
                    {model.providerDisplay}
                  </span>
                </div>

                {!isAvailable && (
                  <span className="shrink-0 rounded border border-line px-1.5 py-0.5 text-[10px] font-medium text-ink-muted">
                    API Key Required
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
