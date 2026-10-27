import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, getHealth, getProfile, listRecommendations, listTransactions } from '../api/client'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import './AppPages.css'

const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const amount = (value) => value == null ? '—' : money.format(Number(value))

export function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      const [healthResult, profileResult, transactionResult, recommendationResult] = await Promise.allSettled([
        getHealth(), getProfile(), listTransactions({ limit: 200 }), listRecommendations(),
      ])
      if (cancelled) return
      if (healthResult.status === 'rejected') setError(healthResult.reason)
      setData({
        health: healthResult.status === 'fulfilled' ? healthResult.value : null,
        profile: profileResult.status === 'fulfilled' ? profileResult.value : null,
        profileMissing: profileResult.status === 'rejected' && profileResult.reason instanceof ApiError && profileResult.reason.status === 404,
        transactions: transactionResult.status === 'fulfilled' ? transactionResult.value : [],
        transactionError: transactionResult.status === 'rejected' ? transactionResult.reason : null,
        recommendations: recommendationResult.status === 'fulfilled' ? recommendationResult.value : [],
      })
      setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [retry])

  const month = new Date().toISOString().slice(0, 7)
  const recent = data?.transactions ?? []
  const monthlyRows = recent.filter((row) => row.transaction_date?.startsWith(month))
  const monthIncome = monthlyRows.filter((row) => row.type === 'income').reduce((sum, row) => sum + Number(row.amount), 0)
  const monthExpenses = monthlyRows.filter((row) => row.type === 'expense').reduce((sum, row) => sum + Number(row.amount), 0)

  return (
    <section className="app-page dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <p className="eyebrow">YOUR FINANCES · FINGUIDE+</p>
          <h1>Your financial picture,<br />layer by layer.</h1>
          <p className="muted">A clear view of the information you have added, with tools to help you make sense of it.</p>
          <div className="dashboard-hero-actions">
            <Link className="button-link primary" to="/chat">Talk it through <span aria-hidden="true">↗</span></Link>
            <Link className="button-link" to="/profile">Update your profile</Link>
          </div>
          <span className="health-chip"><span className="health-dot" /> {data?.health?.status === 'ok' ? 'Services connected' : 'Checking connection'}</span>
        </div>
        <div className="dashboard-art" aria-hidden="true">
          <video className="dashboard-art-video" autoPlay loop muted playsInline preload="metadata" poster="https://d2ol7oe51mr4n9.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/782a4a52-4c1e-4471-bb0c-aa232927f4a6.webp" tabIndex={-1}>
            <source src="https://d2ol7oe51mr4n9.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/435a4fe7-e43b-4e7c-af78-0be083e73569.mp4" type="video/mp4" />
          </video>
          <div className="dashboard-grid-glow" />
          <div className="dashboard-slab dashboard-slab-back"><i /><i /><i /><i /><i /><i /></div>
          <div className="dashboard-slab dashboard-slab-mid"><i /><i /><i /><i /><i /><i /></div>
          <div className="dashboard-slab dashboard-slab-front"><i /><i /><i /><i /><i /><i /></div>
          <div className="dashboard-float-card dashboard-float-top"><span>FINANCIAL PROFILE</span><b>Built around your numbers</b><i /></div>
          <div className="dashboard-float-card dashboard-float-bottom"><span>MARKET CONTEXT</span><b>Evidence, with sources</b><i /></div>
        </div>
      </section>
      {loading && <LoadingState label="Loading your financial overview…" />}
      {error && <ErrorState error={error} onRetry={() => setRetry((count) => count + 1)} />}
      {data && !loading && <>
        {data.profileMissing && <div className="callout"><strong>Start with your financial profile</strong><p>Add your income, expenses, savings, and goals to personalize the overview and recommendations.</p><Link className="button-link primary" to="/profile">Set up profile</Link></div>}
        {data.transactionError && <div className="callout"><strong>Transactions could not be loaded</strong><p>{data.transactionError.message}</p></div>}
        {data.profile && <div className="metric-grid">
          <article className="metric-card"><span>Monthly income in profile</span><strong>{amount(data.profile.monthly_income)}</strong></article>
          <article className="metric-card"><span>Monthly expenses in profile</span><strong>{amount((Number(data.profile.fixed_expenses || 0) + Number(data.profile.variable_expenses || 0)))}</strong></article>
          <article className="metric-card"><span>Savings reported</span><strong>{amount(data.profile.savings)}</strong></article>
          <article className="metric-card"><span>Debt reported</span><strong>{amount(data.profile.debt)}</strong></article>
        </div>}
        <div className="dashboard-columns">
          <section className="panel">
            <div className="panel-heading"><div><h2>This month</h2><p className="muted">From manually recorded transactions</p></div><Link to="/transactions">Manage transactions</Link></div>
            <div className="month-summary"><div><span>Income recorded</span><strong>{money.format(monthIncome)}</strong></div><div><span>Expenses recorded</span><strong>{money.format(monthExpenses)}</strong></div><div><span>Net recorded</span><strong>{money.format(monthIncome - monthExpenses)}</strong></div></div>
            {!recent.length && <p className="empty-state">No transactions yet. <Link to="/transactions">Add your first transaction</Link> to see actual monthly totals here.</p>}
            {recent.length > 0 && <ul className="simple-list">{recent.slice(0, 5).map((row) => <li key={row.id}><div><strong>{row.description || row.category.replaceAll('_', ' ')}</strong><small>{row.transaction_date} · {row.category.replaceAll('_', ' ')}</small></div><strong className={row.type === 'income' ? 'income-text' : ''}>{row.type === 'income' ? '+' : '−'}{money.format(Number(row.amount))}</strong></li>)}</ul>}
          </section>
          <section className="panel">
            <div className="panel-heading"><div><h2>Recommendations</h2><p className="muted">Rule-based checks against your profile</p></div><Link to="/recommendations">Open</Link></div>
            <p className="recommendation-count">{data.recommendations.length} saved recommendation{data.recommendations.length === 1 ? '' : 's'}</p>
            {!data.recommendations.length && <p className="empty-state">Once your profile is set up, run the checks to see whether any rules apply.</p>}
            <Link className="button-link" to="/recommendations">Review recommendations</Link>
          </section>
        </div>
        <p className="fine-print">Profile values are information you entered. Transaction totals reflect only transactions you recorded; they are not bank-imported.</p>
      </>}
    </section>
  )
}
