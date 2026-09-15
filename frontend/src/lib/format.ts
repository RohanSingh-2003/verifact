import type { MutationKind, Verdict, VerifierResponse } from '../types'

export function formatScore(score: number, digits = 2) {
  return score.toFixed(digits)
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function formatPValue(value: number | null | undefined) {
  if (value == null) return 'n/a'
  if (value < 0.001) return '< 0.001'
  return value.toFixed(3)
}

export function shortModelName(model: string, index = 0) {
  const lower = model.toLowerCase()
  if (lower === 'a' || lower.endsWith('-a') || lower.includes('model-a') || lower.includes('model_a')) return 'A'
  if (lower === 'b' || lower.endsWith('-b') || lower.includes('model-b') || lower.includes('model_b')) return 'B'
  return String.fromCharCode(65 + index)
}

export function formatResponseTime(ms: number) {
  return `${(ms / 1000).toFixed(2)}s`
}

export function formatDate(iso: string) {
  const date = new Date(iso)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86_400_000)

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  }).format(date)
}

export function formatTimestamp(iso: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(iso))
}

export function verdictLabel(verdict: Verdict) {
  if (verdict === 'reliable') return 'Reliable'
  if (verdict === 'uncertain') return 'Uncertain'
  return 'Hallucinated'
}

export function verdictDescription(verdict: Verdict) {
  if (verdict === 'reliable') return 'Low likelihood of fact-conflicting hallucination'
  if (verdict === 'uncertain') return 'Inconclusive evidence of fact-conflicting hallucination'
  return 'High likelihood of fact-conflicting hallucination'
}

export function verifierLabel(value: VerifierResponse) {
  if (value === 'yes') return 'YES'
  if (value === 'no') return 'NO'
  return 'NOT SURE'
}

export function mutationKindLabel(kind: MutationKind) {
  return kind === 'synonym' ? 'Synonym' : 'Antonym'
}

export function unexpectedMutation(verifier: VerifierResponse, expected: VerifierResponse) {
  return verifier !== expected
}

export function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}
