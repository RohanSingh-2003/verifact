import { describe, it, expect } from 'vitest'
import { sanitizeExternalUrl } from './format'

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
