import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CollapsibleModelVerdicts } from './CollapsibleModelVerdicts'
import { MutationRow } from './MutationRow'
import type { ModelVerifierVerdictRecord, MutationRecord } from '../../types'
import { MutationKind } from '../../types'

const sampleVerdicts: ModelVerifierVerdictRecord[] = [
  {
    modelId: 'gemma',
    modelName: 'Gemma 4:26B',
    model: 'gemma4:26b',
    provider: 'Ollama Cloud',
    verdict: 'YES',
    rationale: 'Factual claim is verified as true.',
    status: 'completed',
    contribution: 0.0,
  },
  {
    modelId: 'glm',
    modelName: 'GLM-4.7-Flash',
    model: '@cf/zai-org/glm-4.7-flash',
    provider: 'Cloudflare Workers AI',
    verdict: 'NO',
    rationale: 'Claim contradicts established physics.',
    status: 'completed',
    contribution: 1.0,
  },
  {
    modelId: 'qwen',
    modelName: 'Qwen',
    model: 'qwen-2.5-32b',
    provider: 'Alibaba / Groq',
    verdict: 'NOT SURE',
    rationale: '', // empty rationale
    status: 'completed',
    contribution: 0.5,
  },
  {
    modelId: 'openrouter',
    modelName: 'OpenRouter',
    model: 'liquid/lfm-2.5-2.6b:free',
    provider: 'OpenRouter',
    verdict: 'FAILED',
    error: 'API Error: OpenRouter rate-limited the request (HTTP 429)',
    status: 'failed',
    contribution: null,
  },
]

describe('CollapsibleModelVerdicts', () => {
  // 1. Collapsed-by-default behavior
  it('is collapsed by default and shows summary heading with aria-expanded false', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    const trigger = screen.getByRole('button', { name: /AI Verdicts/i })
    expect(trigger).toBeDefined()
    expect(trigger.getAttribute('aria-expanded')).toBe('false')

    // Models should not be visible yet
    expect(screen.queryByText('Gemma 4:26B')).toBeNull()
    expect(screen.queryByText('Factual claim is verified as true.')).toBeNull()
  })

  // 2. Correct dynamic model count and verdict summaries
  it('displays correct dynamic model count and verdict summaries', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    // "4 models verified"
    expect(screen.getByText(/4 models verified/i)).toBeDefined()

    // "YES: 1 · NO: 1 · NOT SURE: 1 · FAILED: 1"
    expect(
      screen.getByText('YES: 1 · NO: 1 · NOT SURE: 1 · FAILED: 1'),
    ).toBeDefined()
  })

  // 3. Clicking expand reveals models, clicking a model entry reveals actual rationale
  it('expanding section reveals models and clicking a model reveals rationale', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    const sectionTrigger = screen.getByRole('button', { name: /AI Verdicts/i })
    fireEvent.click(sectionTrigger)
    expect(sectionTrigger.getAttribute('aria-expanded')).toBe('true')

    // Now model names are visible
    expect(screen.getByText('Gemma 4:26B')).toBeDefined()
    expect(screen.getByText('GLM-4.7-Flash')).toBeDefined()

    // Rationale is not yet expanded
    expect(screen.queryByText(/Factual claim is verified as true/i)).toBeNull()

    // Click Gemma model card
    const gemmaButton = screen.getByRole('button', { name: /Gemma 4:26B/i })
    fireEvent.click(gemmaButton)
    expect(gemmaButton.getAttribute('aria-expanded')).toBe('true')

    // Rationale and provider details are now visible
    expect(screen.getByText(/“Factual claim is verified as true.”/i)).toBeDefined()
    expect(screen.getByText(/Score contribution:/i)).toBeDefined()
  })

  // 4. Clicking the model entry again collapses the explanation
  it('clicking the same model again collapses its explanation', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    fireEvent.click(screen.getByRole('button', { name: /AI Verdicts/i }))
    const gemmaButton = screen.getByRole('button', { name: /Gemma 4:26B/i })

    // Open Gemma
    fireEvent.click(gemmaButton)
    expect(screen.getByText(/“Factual claim is verified as true.”/i)).toBeDefined()

    // Close Gemma
    fireEvent.click(gemmaButton)
    expect(screen.queryByText(/“Factual claim is verified as true.”/i)).toBeNull()
  })

  // 5. At most one model explanation is expanded at a time
  it('allows only one model explanation to be expanded per mutation at a time', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    fireEvent.click(screen.getByRole('button', { name: /AI Verdicts/i }))
    const gemmaButton = screen.getByRole('button', { name: /Gemma 4:26B/i })
    const glmButton = screen.getByRole('button', { name: /GLM-4.7-Flash/i })

    // Expand Gemma
    fireEvent.click(gemmaButton)
    expect(screen.getByText(/“Factual claim is verified as true.”/i)).toBeDefined()

    // Expand GLM
    fireEvent.click(glmButton)
    // GLM explanation should be visible
    expect(screen.getByText(/“Claim contradicts established physics.”/i)).toBeDefined()
    // Gemma explanation should be collapsed
    expect(screen.queryByText(/“Factual claim is verified as true.”/i)).toBeNull()
  })

  // 6. FAILED entries show errors without fabricated rationales
  it('shows error explanation for FAILED entries without fabricating rationale', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    fireEvent.click(screen.getByRole('button', { name: /AI Verdicts/i }))
    const openrouterButton = screen.getByRole('button', { name: /OpenRouter/i })

    fireEvent.click(openrouterButton)
    expect(screen.getByText(/API Error Explanation/i)).toBeDefined()
    expect(
      screen.getByText(/API Error: OpenRouter rate-limited the request \(HTTP 429\)/i),
    ).toBeDefined()
    expect(screen.getByText(/Excluded \(null\)/i)).toBeDefined()
  })

  // 7. Missing rationale shows placeholder without fabricating explanation
  it('displays "No explanation was returned by this model." when rationale is empty', () => {
    render(<CollapsibleModelVerdicts verdicts={sampleVerdicts} mutationId="m-1" />)

    fireEvent.click(screen.getByRole('button', { name: /AI Verdicts/i }))
    const qwenButton = screen.getByRole('button', { name: /Qwen/i })

    fireEvent.click(qwenButton)
    expect(
      screen.getByText('No explanation was returned by this model.'),
    ).toBeDefined()
  })

  // 8. Large model lists render dynamically without errors
  it('handles large model pools (50 models) correctly and computes counts dynamically', () => {
    const largePool: ModelVerifierVerdictRecord[] = Array.from({ length: 50 }, (_, i) => ({
      modelId: `model-${i}`,
      modelName: `Model ${i}`,
      provider: `Provider ${i % 5}`,
      verdict: i % 2 === 0 ? 'YES' : 'NO',
      rationale: `Rationale from Model ${i}`,
      status: 'completed',
      contribution: i % 2 === 0 ? 0.0 : 1.0,
    }))

    render(<CollapsibleModelVerdicts verdicts={largePool} mutationId="large-test" />)

    expect(screen.getByText(/50 models verified/i)).toBeDefined()
    expect(screen.getByText('YES: 25 · NO: 25 · NOT SURE: 0 · FAILED: 0')).toBeDefined()

    // Expand section
    fireEvent.click(screen.getByRole('button', { name: /AI Verdicts/i }))
    expect(screen.getByPlaceholderText(/Filter 50 models/i)).toBeDefined()
  })
})

describe('MutationRow independent state integration', () => {
  // 9. Multiple mutations maintain independent expansion state
  it('maintains independent expansion state across multiple mutations', () => {
    const mut1: MutationRecord = {
      id: 'mut-1',
      kind: MutationKind.Synonym,
      original: 'The Earth orbits the Sun.',
      mutation: 'The Sun is orbited by the Earth.',
      verifier: 'yes',
      expected: 'yes',
      score: 0.0,
      reasoning: 'Synonym test',
      verified: true,
      verdicts: sampleVerdicts,
    }

    const mut2: MutationRecord = {
      id: 'mut-2',
      kind: MutationKind.Antonym,
      original: 'The Earth orbits the Sun.',
      mutation: 'The Sun orbits the Earth.',
      verifier: 'no',
      expected: 'no',
      score: 0.0,
      reasoning: 'Antonym test',
      verified: true,
      verdicts: sampleVerdicts,
    }

    render(
      <div>
        <MutationRow mutation={mut1} index={1} />
        <MutationRow mutation={mut2} index={2} />
      </div>,
    )

    const triggers = screen.getAllByRole('button', { name: /AI Verdicts/i })
    expect(triggers.length).toBe(2)

    // Both are collapsed initially
    expect(triggers[0].getAttribute('aria-expanded')).toBe('false')
    expect(triggers[1].getAttribute('aria-expanded')).toBe('false')

    // Expand only mutation 1
    fireEvent.click(triggers[0])
    expect(triggers[0].getAttribute('aria-expanded')).toBe('true')
    expect(triggers[1].getAttribute('aria-expanded')).toBe('false')

    // Mutation 1 now has model buttons, mutation 2 does not
    const gemmaButtons = screen.getAllByRole('button', { name: /Gemma 4:26B/i })
    expect(gemmaButtons.length).toBe(1)
  })
})
