import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QuestionInput } from './QuestionInput'

describe('QuestionInput', () => {
  it('does NOT render any model selection dropdown or selector button', () => {
    const handleChange = vi.fn()
    const handleSubmit = vi.fn()

    render(
      <QuestionInput
        value=""
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    )

    // No dropdown, select, or model picker buttons
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.queryByText(/Select Model/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /Gemma 4:26B/i })).toBeNull()

    // Shows static non-interactive indicator
    expect(screen.getByText(/Answered by Gemma 4:26B/i)).toBeDefined()
  })

  it('allows entering a question and triggers analyze callback on submit', () => {
    const handleChange = vi.fn()
    const handleSubmit = vi.fn()

    render(
      <QuestionInput
        value="What is the capital of Australia?"
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    )

    const textarea = screen.getByRole('textbox', { name: /Question/i })
    expect(textarea).toBeDefined()

    const submitButton = screen.getByRole('button', { name: /Analyze Answer/i })
    expect(submitButton).toBeDefined()
    expect(submitButton.hasAttribute('disabled')).toBe(false)

    fireEvent.click(submitButton)
    expect(handleSubmit).toHaveBeenCalledTimes(1)
  })
})
