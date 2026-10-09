import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { AnswerModelOption } from '../../types'

interface AnswerModelSelectorProps {
  models: AnswerModelOption[]
  selectedId: string
  onSelect: (modelId: string) => void
  disabled?: boolean
  className?: string
}

export function AnswerModelSelector({
  models,
  selectedId,
  onSelect,
  disabled = false,
  className = '',
}: AnswerModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [placement, setPlacement] = useState<'top' | 'bottom'>('top')
  const [focusedIndex, setFocusedIndex] = useState<number>(-1)

  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const listboxRef = useRef<HTMLUListElement>(null)

  const selectedModel =
    models.find((m) => m.id === selectedId) ??
    models[0] ?? {
      id: 'gemma',
      name: 'Gemma 4:26B',
      provider: 'ollama',
      providerDisplay: 'Ollama Cloud',
      configured: true,
    }

  // Calculate placement (open upward by default, or downward if too close to viewport top)
  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect()
      // If less than 280px above viewport and more space below, flip downward
      if (rect.top < 280 && window.innerHeight - rect.bottom > rect.top) {
        setPlacement('bottom')
      } else {
        setPlacement('top')
      }
    }
  }, [isOpen])

  function handleToggleOpen() {
    if (!isOpen) {
      const idx = models.findIndex((m) => m.id === selectedModel.id)
      setFocusedIndex(idx >= 0 ? idx : 0)
    }
    setIsOpen((prev) => !prev)
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

  // Global escape key listener
  useEffect(() => {
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
        buttonRef.current?.focus()
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  function handleButtonKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === ' ') {
      event.preventDefault()
      const idx = models.findIndex((m) => m.id === selectedModel.id)
      setFocusedIndex(idx >= 0 ? idx : 0)
      setIsOpen(true)
    }
  }

  function handleListKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    if (event.key === 'Tab') {
      setIsOpen(false)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      setFocusedIndex((prev) => (prev + 1) % models.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setFocusedIndex((prev) => (prev - 1 + models.length) % models.length)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (focusedIndex >= 0 && focusedIndex < models.length) {
        const target = models[focusedIndex]
        if (target.configured && !disabled) {
          onSelect(target.id)
          setIsOpen(false)
          buttonRef.current?.focus()
        }
      }
    }
  }

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      {/* Compact Trigger Button inside Input Toolbar */}
      <button
        ref={buttonRef}
        type="button"
        id="answer-model-selector-button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls="answer-model-listbox"
        aria-label={`Answer Model: ${selectedModel.name}, provider: ${selectedModel.providerDisplay}`}
        disabled={disabled}
        onClick={handleToggleOpen}
        onKeyDown={handleButtonKeyDown}
        className="inline-flex h-8 max-w-full items-center gap-2 rounded-[var(--radius-sm)] border border-line bg-surface px-2.5 py-1 text-left text-xs font-medium text-ink transition-colors hover:border-line-strong hover:bg-surface-muted/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate max-w-[125px] sm:max-w-[170px] text-ink font-medium">
          {selectedModel.name}
        </span>
        <span className="truncate max-w-[85px] sm:max-w-[130px] text-[11px] text-ink-muted hidden xs:inline">
          {selectedModel.providerDisplay}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-ink-muted transition-transform duration-150 ${
            isOpen ? 'rotate-180 text-ink' : ''
          }`}
          strokeWidth={1.75}
        />
      </button>

      {/* Popover / Dropdown Menu */}
      {isOpen && (
        <div
          className={`absolute z-50 w-72 sm:w-84 max-w-[calc(100vw-2.5rem)] rounded-[var(--radius-sm)] border border-line bg-surface p-1.5 shadow-[var(--shadow-float)] animate-fade-up focus:outline-none ${
            placement === 'top' ? 'bottom-full mb-2 left-0' : 'top-full mt-2 left-0'
          }`}
        >
          <div className="mb-1 flex items-center justify-between border-b border-line/60 px-2.5 pb-1.5 pt-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            <span>Answer Model</span>
            <span className="text-[10px] font-normal lowercase tracking-normal text-ink-muted/80">
              4 independent verifiers
            </span>
          </div>

          <ul
            ref={listboxRef}
            id="answer-model-listbox"
            role="listbox"
            aria-label="Available Answer Models"
            tabIndex={0}
            onKeyDown={handleListKeyDown}
            className="max-h-72 overflow-y-auto focus:outline-none"
          >
            {models.map((model, idx) => {
              const isSelected = model.id === selectedModel.id
              const isAvailable = model.configured
              const isFocused = idx === focusedIndex

              return (
                <li
                  key={model.id}
                  id={`answer-model-option-${model.id}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={!isAvailable}
                  onClick={() => {
                    if (!isAvailable || disabled) return
                    onSelect(model.id)
                    setIsOpen(false)
                    buttonRef.current?.focus()
                  }}
                  onMouseEnter={() => setFocusedIndex(idx)}
                  className={`flex cursor-pointer items-center justify-between gap-2.5 rounded-[var(--radius-sm)] px-2.5 py-2 text-xs transition-colors ${
                    !isAvailable
                      ? 'cursor-not-allowed opacity-50'
                      : isSelected
                        ? 'bg-surface-muted text-ink font-medium'
                        : isFocused
                          ? 'bg-surface-muted/60 text-ink'
                          : 'text-ink hover:bg-surface-muted/60'
                  }`}
                >
                  <div className="flex min-w-0 items-center gap-2">
                    {isSelected ? (
                      <Check className="h-3.5 w-3.5 text-accent shrink-0" strokeWidth={2.5} />
                    ) : (
                      <span className="w-3.5 shrink-0" />
                    )}
                    <span className="truncate font-medium text-ink">{model.name}</span>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-[11px] text-ink-muted">{model.providerDisplay}</span>
                    {!isAvailable && (
                      <span className="rounded border border-line bg-surface-muted/40 px-1.5 py-0.5 text-[10px] font-medium text-ink-muted">
                        API Key Required
                      </span>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>

          <div className="mt-1 border-t border-line/50 px-2.5 pt-1.5 text-[10px] text-ink-muted">
            Independent verifiers assigned dynamically
          </div>
        </div>
      )}
    </div>
  )
}
