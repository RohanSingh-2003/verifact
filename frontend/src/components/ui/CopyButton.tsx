import { useState } from 'react'
import { classNames } from '../../lib/format'

interface CopyButtonProps {
  value: string
  label?: string
}

export function CopyButton({ value, label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      className={classNames(
        'rounded-md px-2 py-1 text-xs font-medium transition-colors',
        copied ? 'text-accent' : 'text-ink-muted hover:bg-surface-muted hover:text-ink',
      )}
      aria-label={copied ? 'Copied to clipboard' : label}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}
