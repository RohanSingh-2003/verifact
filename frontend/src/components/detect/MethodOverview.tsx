import { ChevronRight } from 'lucide-react'

const STEPS = [
  'Generate answer',
  'Create synonym and antonym mutations',
  'Verify mutations',
  'Calculate MetaQA score',
  'Compare with threshold',
] as const

export function MethodOverview() {
  return (
    <details className="group mb-6">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-ink-secondary marker:content-none [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="h-3.5 w-3.5 text-ink-muted transition-transform group-open:rotate-90"
          strokeWidth={1.75}
          aria-hidden="true"
        />
        How this works
      </summary>
      <ol className="mt-3 grid gap-2 sm:grid-cols-5">
        {STEPS.map((step, index) => (
          <li key={step} className="flex gap-2 text-xs leading-5 text-ink-secondary sm:block">
            <span className="font-medium text-ink">{index + 1}</span>
            <span className="sm:mt-1 sm:block">{step}</span>
          </li>
        ))}
      </ol>
    </details>
  )
}
