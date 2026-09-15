import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRuns } from '../services/api'
import { HistoryTable } from '../components/history/HistoryTable'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/Status'
import type { HistoryRun, Verdict } from '../types'

export function HistoryPage() {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<HistoryRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [verdictFilter, setVerdictFilter] = useState<Verdict | 'all'>('all')

  useEffect(() => {
    let cancelled = false
    void getRuns()
      .then((data) => {
        if (!cancelled) setRuns(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load run history. Check that the FastAPI server is running.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return runs.filter((run) => {
      const matchesQuery = !needle || run.question.toLowerCase().includes(needle)
      const matchesVerdict = verdictFilter === 'all' || run.verdict === verdictFilter
      return matchesQuery && matchesVerdict
    })
  }, [query, runs, verdictFilter])

  return (
    <div>
      <PageHeader title="Run History" description="Review previous hallucination analyses." />

      {loading ? <LoadingState label="Loading run history…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !error ? (
        <HistoryTable
          runs={filtered}
          onSelect={(id) => navigate(`/?id=${id}`)}
          query={query}
          onQueryChange={setQuery}
          verdictFilter={verdictFilter}
          onVerdictFilterChange={setVerdictFilter}
        />
      ) : null}
    </div>
  )
}
