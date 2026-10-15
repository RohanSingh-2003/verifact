import { describe, it, expect } from 'vitest'
import { sanitizeExternalUrl, formatProviderDisplay, formatVerifierProvider } from './format'

describe('sanitizeExternalUrl', () => {
  it('accepts valid http and https URLs', () => {
    expect(sanitizeExternalUrl('https://example.com/article')).toBe('https://example.com/article')
    expect(sanitizeExternalUrl('http://example.com/page?id=123&sort=asc')).toBe('http://example.com/page?id=123&sort=asc')
    expect(sanitizeExternalUrl('https://subdomain.domain.org/path/to/resource#section')).toBe('https://subdomain.domain.org/path/to/resource#section')
    expect(sanitizeExternalUrl('https://en.wikipedia.org/wiki/Canberra')).toBe('https://en.wikipedia.org/wiki/Canberra')
  })

  it('trims leading and trailing whitespace around valid URLs', () => {
    expect(sanitizeExternalUrl('   https://example.com/trimmed   ')).toBe('https://example.com/trimmed')
    expect(sanitizeExternalUrl('\n\thttps://example.com/spaced\t')).toBe('https://example.com/spaced')
  })

  it('rejects unsafe schemes including javascript, data, and vbscript', () => {
    expect(sanitizeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(sanitizeExternalUrl('javascript:void(0)')).toBeNull()
    expect(sanitizeExternalUrl('JAVASCRIPT:alert(document.cookie)')).toBeNull()
    expect(sanitizeExternalUrl('javascript://example.com/%0Aalert(1)')).toBeNull()
    expect(sanitizeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(sanitizeExternalUrl('DATA:text/plain;base64,SGVsbG8=')).toBeNull()
    expect(sanitizeExternalUrl('vbscript:msgbox("hello")')).toBeNull()
  })

  it('rejects local file and relative URLs', () => {
    expect(sanitizeExternalUrl('file:///etc/passwd')).toBeNull()
    expect(sanitizeExternalUrl('file:///C:/Windows/win.ini')).toBeNull()
    expect(sanitizeExternalUrl('/relative/path')).toBeNull()
    expect(sanitizeExternalUrl('../parent/path')).toBeNull()
    expect(sanitizeExternalUrl('relative/without/slash')).toBeNull()
  })

  it('rejects malformed, empty, and non-string inputs', () => {
    expect(sanitizeExternalUrl('')).toBeNull()
    expect(sanitizeExternalUrl('   ')).toBeNull()
    expect(sanitizeExternalUrl(null)).toBeNull()
    expect(sanitizeExternalUrl(undefined)).toBeNull()
    expect(sanitizeExternalUrl('not a url')).toBeNull()
    expect(sanitizeExternalUrl('htp://invalid-scheme')).toBeNull()
    expect(sanitizeExternalUrl('https://')).toBeNull()
    expect(sanitizeExternalUrl('http://')).toBeNull()
  })
})

describe('formatVerifierProvider & formatProviderDisplay', () => {
  it('formats Liquid verifier as Liquid (Liquid AI)', () => {
    expect(formatVerifierProvider('openrouter', 'OpenRouter', 'openrouter')).toBe('Liquid (Liquid AI)')
    expect(formatVerifierProvider('OpenRouter', 'liquid/lfm-2.5-2.6b:free', 'openrouter')).toBe('Liquid (Liquid AI)')
    expect(formatVerifierProvider('Liquid (Liquid AI)', 'OpenRouter', 'openrouter')).toBe('Liquid (Liquid AI)')
    expect(formatProviderDisplay('openrouter', 'liquid/lfm-2.5-2.6b:free')).toBe('Liquid (Liquid AI)')
  })

  it('formats Phi-4 Reasoning verifier as Microsoft', () => {
    expect(formatVerifierProvider('openrouter', 'Phi-4 Reasoning', 'phi')).toBe('Microsoft')
    expect(formatVerifierProvider('OpenRouter', 'microsoft/phi-4-reasoning:free', 'phi')).toBe('Microsoft')
    expect(formatVerifierProvider('Microsoft', 'Phi-4 Reasoning', 'phi')).toBe('Microsoft')
    expect(formatProviderDisplay('openrouter', 'microsoft/phi-4-reasoning:free')).toBe('Microsoft')
  })

  it('preserves GLM and Qwen labels unchanged', () => {
    expect(formatVerifierProvider('Cloudflare Workers AI', 'GLM-4.7-Flash', 'glm')).toBe('Cloudflare Workers AI')
    expect(formatVerifierProvider('cloudflare', '@cf/zai-org/glm-4.7-flash', 'glm')).toBe('Cloudflare Workers AI')
    expect(formatVerifierProvider('Alibaba / Groq', 'Qwen', 'qwen')).toBe('Alibaba / Groq')
    expect(formatVerifierProvider('groq', 'qwen-2.5-32b', 'qwen')).toBe('Alibaba / Groq')
  })
})
