import { useCallback, useEffect, useState } from 'react'
import { getOfficialFinancialUpdates } from '../api/client'
import { ErrorState } from './ErrorState'

function formatCategory(category) {
  return String(category).replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase())
}

function formatDate(value) {
  if (!value) return 'Publisher date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Publisher date unavailable' : date.toLocaleString('en-IN')
}

export function OfficialUpdatesPanel({ compact = false }) {
  const [updates, setUpdates] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setUpdates(await getOfficialFinancialUpdates())
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <aside className={`panel official-updates-panel official-updates-rail${compact ? ' official-updates-compact' : ''}`} aria-labelledby="official-updates-title">
      <div className="official-rail-heading">
        <div>
          <p className="eyebrow">REGULATORY SIGNALS</p>
          <h2 id="official-updates-title">Official financial updates</h2>
          <p>Recent RBI and SEBI headlines, linked to their publishers.</p>
        </div>
        <button type="button" onClick={refresh} disabled={loading} aria-label="Refresh official financial updates">
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {loading && !updates && <p className="muted" role="status">Fetching publisher updates…</p>}
      {error && <ErrorState error={error} onRetry={refresh} />}
      {updates && <>
        <p className="official-rail-meta">
          Updated {formatDate(updates.retrieved_at)} · {updates.articles.length} headline{updates.articles.length === 1 ? '' : 's'}
        </p>
        <p className="official-rail-note">{updates.analysis_note}</p>
        {updates.articles.length > 0 ? (
          <ul className="official-news-list">
            {updates.articles.map((article) => (
              <li key={article.id}>
                <div className="official-news-item">
                  <a href={article.source_url} target="_blank" rel="noreferrer"><strong>{article.title}</strong></a>
                  <small>{article.source_name} · {formatDate(article.published_at)}</small>
                  {article.summary && <p>{article.summary}</p>}
                  <span className={`news-freshness news-freshness-${article.freshness_status}`}>{article.freshness_status} by publisher date</span>
                  {article.topics?.length > 0 && <span className="news-topics">{article.topics.map(formatCategory).join(' · ')}</span>}
                  {article.sentiment && <span className={`news-sentiment news-sentiment-${article.sentiment.label}`}>Headline tone: {article.sentiment.label}{article.sentiment.confidence != null ? ` · ${(article.sentiment.confidence * 100).toFixed(0)}%` : ''}</span>}
                  {article.additional_sources?.map((source) => <small key={source.source_url}>Also reported by <a href={source.source_url} target="_blank" rel="noreferrer">{source.source_name}</a></small>)}
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="market-research-notice">No headlines returned. Check the publisher status below.</p>}
        <details className="official-source-status">
          <summary>Publisher feed status</summary>
          <ul>{updates.sources.map((source) => <li key={source.source_id}>
            <span>{source.source_name}: {source.status === 'available' ? `${source.items_returned} items` : source.reason}</span>{' '}
            <a href={source.feed_url} target="_blank" rel="noreferrer">RSS feed</a>
          </li>)}</ul>
        </details>
      </>}
    </aside>
  )
}
