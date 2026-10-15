import type { MutationKind, Verdict, VerifierResponse } from '../types'

export function formatScore(score: number | null | undefined, digits = 2) {
  if (score == null || Number.isNaN(score)) return '—'
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
  if (verdict === 'reliable') return 'Likely reliable'
  if (verdict === 'uncertain') return 'Uncertain'
  return 'Likely hallucinated'
}

export function verdictDescription(verdict: Verdict) {
  if (verdict === 'reliable') {
    return 'The mutation tests were mostly consistent with the expected behavior.'
  }
  if (verdict === 'uncertain') {
    return 'The mutation tests did not produce a clear consistency pattern.'
  }
  return 'The mutation tests showed behavior that is inconsistent with the expected pattern.'
}

export function formatModelDisplay(model: string | null | undefined): string | null {
  if (!model) return null
  const gemmaMatch = model.match(/^gemma4:(.+)$/i)
  if (gemmaMatch) return `Gemma 4:${gemmaMatch[1].toUpperCase()}`
  const gemma3Match = model.match(/^gemma3:(.+)$/i)
  if (gemma3Match) return `Gemma 3:${gemma3Match[1].toUpperCase()}`
  const geminiMatch = model.match(/^gemini-(\d+(?:\.\d+)?)-([a-z0-9_-]+)$/i)
  if (geminiMatch) {
    const capitalizedType = geminiMatch[2].charAt(0).toUpperCase() + geminiMatch[2].slice(1)
    return `Gemini ${geminiMatch[1]} ${capitalizedType}`
  }
  if (model.toLowerCase().includes('phi-4') || model.toLowerCase().includes('phi')) {
    return 'Phi-4 Reasoning'
  }
  return model
}

export function formatProviderDisplay(provider: string | null | undefined, model?: string): string {
  const normModel = (model || '').toLowerCase()
  if (normModel.includes('microsoft') || normModel.includes('phi')) return 'Microsoft'
  if (normModel.includes('liquid') || normModel.includes('lfm')) return 'Liquid (Liquid AI)'
  if (normModel.includes('gemini')) return 'Google'
  if (provider === 'Microsoft' || provider === 'Liquid (Liquid AI)') return provider
  if (!provider) return ''
  if (provider === 'ollama') return 'Ollama Cloud'
  if (provider === 'cloudflare') return 'Cloudflare Workers AI'
  if (provider === 'groq') return 'Alibaba / Groq'
  if (provider === 'openrouter') return 'OpenRouter'
  if (provider === 'gemini') return 'Google'
  if (provider === 'openai_compatible') return 'OpenAI Compatible'
  return provider.charAt(0).toUpperCase() + provider.slice(1)
}

export function formatVerifierProvider(
  provider: string | null | undefined,
  modelName?: string,
  modelId?: string,
): string {
  if (provider === 'Microsoft' || provider === 'Liquid (Liquid AI)') {
    return provider
  }

  const candidate = `${modelId || ''} ${modelName || ''} ${provider || ''}`.toLowerCase()
  if (candidate.includes('microsoft') || candidate.includes('phi')) {
    return 'Microsoft'
  }
  if (
    candidate.includes('liquid') ||
    candidate.includes('lfm') ||
    modelId?.toLowerCase() === 'openrouter' ||
    modelName?.toLowerCase() === 'openrouter'
  ) {
    return 'Liquid (Liquid AI)'
  }
  if (candidate.includes('cloudflare') || candidate.includes('glm')) {
    return 'Cloudflare Workers AI'
  }
  if (candidate.includes('groq') || candidate.includes('qwen') || candidate.includes('alibaba')) {
    return 'Alibaba / Groq'
  }
  if (candidate.includes('ollama') || candidate.includes('gemma')) {
    return 'Ollama Cloud'
  }

  return formatProviderDisplay(provider, modelName)
}

export function verifierLabel(value: VerifierResponse) {
  if (value === 'yes') return 'YES'
  if (value === 'no') return 'NO'
  return 'NOT SURE'
}

export function mutationKindLabel(kind: MutationKind) {
  return kind === 'synonym' ? 'Synonym' : 'Antonym'
}

export function unexpectedMutation(
  verifier: VerifierResponse | null | undefined,
  expected: VerifierResponse,
) {
  if (verifier == null) return false
  return verifier !== expected
}

export function mutationMeaningLabel(kind: MutationKind) {
  return kind === 'synonym'
    ? 'Same meaning — the wording was changed while the factual claim remains the same.'
    : 'Opposite meaning — the mutation contradicts the original claim.'
}

export function mutationExpectationLabel(kind: MutationKind) {
  return kind === 'synonym'
    ? 'The mutation preserves the original claim, so the verifier is expected to accept it.'
    : 'The mutation contradicts the original claim, so the verifier is expected to reject it.'
}

/** Deterministic UI copy only — does not affect MetaQA scoring. */
export function mutationInterpretation(
  kind: MutationKind,
  verifier: VerifierResponse | null | undefined,
  expected: VerifierResponse,
): string {
  if (verifier == null) {
    return 'Waiting for the verifier result for this mutation.'
  }
  if (verifier === 'not_sure') {
    return kind === 'synonym'
      ? 'The verifier was uncertain about a mutation that should preserve the original meaning.'
      : 'The verifier was uncertain about a mutation that should contradict the original claim.'
  }
  const matches = verifier === expected
  if (kind === 'synonym') {
    return matches
      ? 'The verifier accepted the mutation as consistent with the original claim.'
      : 'The verifier rejected a mutation that should preserve the original meaning.'
  }
  return matches
    ? 'The verifier rejected the contradiction as expected.'
    : 'The verifier accepted a mutation that should contradict the original claim.'
}

export function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

/**
 * Validates and sanitizes external web evidence URLs.
 * Accepts only absolute, parseable URLs with http: and https: protocols.
 * Returns the normalized URL string, or null for empty, missing, malformed, relative, or unsafe URLs.
 */
export function sanitizeExternalUrl(url: string | null | undefined): string | null {
  if (!url || typeof url !== 'string') return null
  const trimmed = url.trim()
  if (!trimmed) return null
  try {
    const parsed = new URL(trimmed)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href
    }
    return null
  } catch {
    return null
  }
}
