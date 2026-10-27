import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  evaluatePendingRecommendations,
  evaluateRecommendation,
  createMutualFundGoalPlan,
  generateRecommendations,
  getMarketResearchShortlist,
  getRecommendationExplanation,
  listRecommendations,
  listHoldings,
  presentRecommendation,
  submitRecommendationFeedback,
} from '../api/client'
import { OfficialUpdatesPanel } from '../components/OfficialUpdatesPanel'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import './Recommendations.css'

const STATUS_LABEL = {
  CANDIDATE: 'Needs review',
  APPROVE: 'Approved',
  CLARIFY: 'Needs more info',
  EDUCATE: 'General guidance',
  LIMIT: 'Approved, limited',
  BLOCK: 'Blocked',
  ESCALATE: 'Escalated for review',
}

const STATUS_CLASS = {
  CANDIDATE: 'status-candidate',
  APPROVE: 'status-approved',
  CLARIFY: 'status-clarify',
  EDUCATE: 'status-educate',
  LIMIT: 'status-limit',
  BLOCK: 'status-blocked',
  ESCALATE: 'status-escalate',
}

const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

function formatRupees(value) {
  return INR.format(Number(value ?? 0))
}

function displayStatus(rec) {
  return rec.suitability_status ?? 'CANDIDATE'
}

function formatCategory(category) {
  return category.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function Recommendations() {
  const [recs, setRecs] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const [generating, setGenerating] = useState(false)
  const [genNotice, setGenNotice] = useState(null)

  const [reviewingAll, setReviewingAll] = useState(false)
  const [reviewingId, setReviewingId] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [lifecycleId, setLifecycleId] = useState(null)

  const [expandedId, setExpandedId] = useState(null)
  const [explanations, setExplanations] = useState({})
  const [explanationLoading, setExplanationLoading] = useState(null)

  const [marketResearch, setMarketResearch] = useState(null)
  const [portfolioContext, setPortfolioContext] = useState({ schemeCodes: new Set(), categories: new Map() })
  const [marketLoading, setMarketLoading] = useState(false)
  const [marketError, setMarketError] = useState(null)
  const [goalForm, setGoalForm] = useState({ goal_name: '', target_amount: '', current_savings: '0', monthly_contribution: '0', years: '5' })
  const [goalPlan, setGoalPlan] = useState(null)
  const [goalPlanLoading, setGoalPlanLoading] = useState(false)
  const [goalPlanError, setGoalPlanError] = useState(null)

  // Mirrors useApi.js's own shape (fetch inlined directly in the effect)
  // rather than calling out to a separately-defined function — `refetch`
  // below is a plain async function used only for post-mutation
  // refreshes (button handlers), not referenced by this effect. No
  // `setLoading(true)` here: `loading` already starts `true` via
  // useState(true) above, so setting it again on mount would be a
  // same-value no-op — this is a mount-only effect (empty deps), not a
  // re-triggerable one that would need loading reset each run.
  useEffect(() => {
    let cancelled = false
    listRecommendations()
      .then((data) => {
        if (cancelled) return
        setRecs(data)
        setLoadError(null)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    listHoldings().then((items) => {
      if (!cancelled) {
        const categories = new Map()
        for (const item of items) {
          const category = item.scheme_category?.trim().toLowerCase()
          if (category) categories.set(category, (categories.get(category) || 0) + 1)
        }
        setPortfolioContext({ schemeCodes: new Set(items.map((item) => Number(item.scheme_code))), categories })
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Load the market screen automatically so the page does not look empty
  // until the user discovers a separate action button. The endpoint returns
  // profile requirements before contacting market-data providers.
  useEffect(() => {
    let cancelled = false
    setMarketLoading(true)
    getMarketResearchShortlist()
      .then((data) => {
        if (!cancelled) setMarketResearch(data)
      })
      .catch((err) => {
        if (!cancelled) setMarketError(err)
      })
      .finally(() => {
        if (!cancelled) setMarketLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function refetch() {
    try {
      const data = await listRecommendations()
      setRecs(data)
      setLoadError(null)
    } catch (err) {
      setLoadError(err)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    setGenNotice(null)
    setActionError(null)
    try {
      const result = await generateRecommendations()
      if (result.context_status === 'NO_METRICS_COMPUTED') {
        setGenNotice({
          type: 'no-data',
          message:
            "We don't have enough financial data yet to check for recommendations.",
        })
      } else {
        const triggered = result.candidates.length
        const checked = triggered + result.skipped.length
        setGenNotice({
          type: 'ok',
          message:
            triggered > 0
              ? `Checked ${checked} rule${checked === 1 ? '' : 's'} — ${triggered} triggered.`
              : `Checked ${checked} rule${checked === 1 ? '' : 's'} — nothing to flag right now.`,
        })
        await refetch()
      }
    } catch (err) {
      setActionError(err)
    } finally {
      setGenerating(false)
    }
  }

  async function handleMarketResearch() {
    setMarketLoading(true)
    setMarketError(null)
    try {
      setMarketResearch(await getMarketResearchShortlist())
    } catch (err) {
      setMarketError(err)
    } finally {
      setMarketLoading(false)
    }
  }

  async function handleGoalPlan(event) {
    event.preventDefault()
    setGoalPlanLoading(true)
    setGoalPlanError(null)
    try {
      const result = await createMutualFundGoalPlan({
        ...goalForm,
        target_amount: Number(goalForm.target_amount),
        current_savings: Number(goalForm.current_savings || 0),
        monthly_contribution: Number(goalForm.monthly_contribution || 0),
        years: Number(goalForm.years),
      })
      setGoalPlan(result.goal_plan)
      setMarketResearch(result.market_research)
      setMarketError(null)
    } catch (err) {
      setGoalPlanError(err)
    } finally {
      setGoalPlanLoading(false)
    }
  }

  async function handleReviewAll() {
    setReviewingAll(true)
    setActionError(null)
    try {
      await evaluatePendingRecommendations()
      await refetch()
    } catch (err) {
      setActionError(err)
    } finally {
      setReviewingAll(false)
    }
  }

  async function handleReviewOne(id) {
    setReviewingId(id)
    setActionError(null)
    try {
      await evaluateRecommendation(id)
      await refetch()
    } catch (err) {
      setActionError(err)
    } finally {
      setReviewingId(null)
    }
  }

  async function handlePresent(id) {
    setLifecycleId(id)
    setActionError(null)
    try {
      await presentRecommendation(id)
      await refetch()
    } catch (err) {
      setActionError(err)
    } finally {
      setLifecycleId(null)
    }
  }

  async function handleFeedback(id, action, rating) {
    setLifecycleId(id)
    setActionError(null)
    try {
      await submitRecommendationFeedback(id, { action, rating })
      await refetch()
    } catch (err) {
      setActionError(err)
    } finally {
      setLifecycleId(null)
    }
  }

  async function handleToggleExplain(id) {
    if (expandedId === id) {
      setExpandedId(null)
      return
    }
    setExpandedId(id)
    if (!explanations[id]) {
      setExplanationLoading(id)
      try {
        const explanation = await getRecommendationExplanation(id)
        setExplanations((prev) => ({ ...prev, [id]: explanation }))
      } catch (err) {
        setExplanations((prev) => ({ ...prev, [id]: { error: err } }))
      } finally {
        setExplanationLoading(null)
      }
    }
  }

  if (loading && !recs) return <LoadingState label="Loading recommendations…" />
  if (loadError) return <ErrorState error={loadError} onRetry={refetch} />

  const hasCandidates = recs?.some((r) => r.state === 'candidate')

  return (
    <section className="recs-page">
      <div className="recs-header">
        <div>
          <h1>Recommendations</h1>
          <p className="recs-intro">
            Profile-based financial observations and a separate, source-attributed
            market research shortlist for user/adviser review. Market candidates are
            not approved investment advice.
          </p>
        </div>
      </div>

      <section className="market-research" aria-labelledby="market-research-title">
        <div className="market-research-heading">
          <div>
            <h2 id="market-research-title">Current market research</h2>
            <p>Free-source research across Indian mutual-fund NAVs, including index, equity, debt, and gold-fund categories where data is available.</p>
          </div>
          <button type="button" className="primary" onClick={handleMarketResearch} disabled={marketLoading}>
            {marketLoading ? 'Checking sources…' : marketResearch ? 'Refresh research' : 'Check market research'}
          </button>
        </div>
        <form className="goal-plan-form" onSubmit={handleGoalPlan}>
          <h3>Plan toward a financial goal</h3>
          <p>Enter a target and timeline. FinGuide will calculate a simple savings baseline and screen fund research against your profile and this goal horizon.</p>
          <div className="goal-plan-fields">
            <label>
              Goal name
              <input required minLength="2" maxLength="120" value={goalForm.goal_name} onChange={(event) => setGoalForm({ ...goalForm, goal_name: event.target.value })} placeholder="e.g. Further education" />
            </label>
            <label>
              Target amount (₹)
              <input required type="number" min="1" step="1" value={goalForm.target_amount} onChange={(event) => setGoalForm({ ...goalForm, target_amount: event.target.value })} />
            </label>
            <label>
              Already saved for this goal (₹)
              <input type="number" min="0" step="1" value={goalForm.current_savings} onChange={(event) => setGoalForm({ ...goalForm, current_savings: event.target.value })} />
            </label>
            <label>
              Planned monthly saving (₹)
              <input type="number" min="0" step="1" value={goalForm.monthly_contribution} onChange={(event) => setGoalForm({ ...goalForm, monthly_contribution: event.target.value })} />
            </label>
            <label>
              Time to goal (years)
              <input required type="number" min="1" max="50" step="1" value={goalForm.years} onChange={(event) => setGoalForm({ ...goalForm, years: event.target.value })} />
            </label>
          </div>
          <button className="primary" type="submit" disabled={goalPlanLoading || !goalForm.target_amount}>
            {goalPlanLoading ? 'Building your plan…' : 'Build goal plan'}
          </button>
          {goalPlanError && <ErrorState error={goalPlanError} />}
          {goalPlan && (
            <div className="goal-plan-result" aria-live="polite">
              <h4>{goalPlan.goal_name}: planning baseline</h4>
              <dl>
                <dt>Amount remaining</dt><dd>{formatRupees(goalPlan.remaining_amount)}</dd>
                <dt>Monthly savings baseline, assuming zero growth</dt><dd>{formatRupees(goalPlan.monthly_savings_baseline)}</dd>
                <dt>Your planned monthly saving</dt><dd>{formatRupees(goalPlan.planned_monthly_contribution)}</dd>
                <dt>Difference from baseline</dt><dd>{formatRupees(goalPlan.monthly_baseline_gap)}</dd>
              </dl>
              <p><strong>{goalPlan.pace_message}</strong></p>
              <p className="market-research-meta">{goalPlan.calculation_note}</p>
              <p className="market-research-meta">{goalPlan.research_note}</p>
              {marketResearch?.candidates?.length > 0 ? (
                <div className="goal-plan-shortlist">
                  <h4>Fund research for this goal timeline</h4>
                  <p className="market-research-meta">{marketResearch.candidates.length} sourced candidate(s) passed the current profile and data screens. These are research options, not instructions to invest.</p>
                  <ol>
                    {marketResearch.candidates.slice(0, 3).map((candidate) => (
                      <li key={candidate.scheme_code}>
                        <strong>{candidate.scheme_name}</strong>
                        <span>{candidate.scheme_category}</span>
                        <span>
                          {candidate.relative_rank != null ? `Category rank ${candidate.relative_rank} of ${candidate.peer_count}` : 'Not enough same-category peers to rank'}
                          {candidate.research_score != null ? ` · Comparative score ${candidate.research_score}/100` : ''}
                        </span>
                        <span>3-year historical NAV return {candidate.return_3y_cagr_percent}% · drawdown {candidate.max_drawdown_3y_percent ?? 'Unavailable'}%</span>
                        <a href={candidate.source_url} target="_blank" rel="noreferrer">Check source data</a>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : marketResearch?.status === 'needs_profile' ? (
                <p className="goal-plan-blocker">No fund candidates yet. Complete the profile fields needed for screening: {marketResearch.profile_fields_needed?.join(', ').replaceAll('_', ' ') || 'required financial profile data'}.</p>
              ) : marketResearch?.suitability_gate?.status === 'hold' ? (
                <p className="goal-plan-blocker">Fund research is currently held: {marketResearch.suitability_gate.detail}</p>
              ) : marketResearch ? (
                <p className="goal-plan-blocker">No fund candidates are shown because current NAV data or the screening criteria did not produce a verifiable shortlist. Check the market-data status and limitations below.</p>
              ) : null}
            </div>
          )}
        </form>
        <OfficialUpdatesPanel />
        {marketLoading && !marketResearch && <p className="market-research-notice">Loading profile and market-data availability…</p>}
        {marketError?.status === 404 ? (
          <p className="market-research-notice">
            Add your financial profile before building a shortlist. <Link to="/profile">Open profile</Link>
          </p>
        ) : marketError ? <ErrorState error={marketError} /> : null}
        {marketResearch && (
          <div className="market-research-results">
            <p className="market-research-notice">{marketResearch.research_notice}</p>
            {marketResearch.ranking_method && <p className="market-research-notice">{marketResearch.ranking_method} A score is not a probability or a return forecast.</p>}
            {marketResearch.index_snapshot && (
              <div className="market-index-snapshot">
                <h3>NIFTY 50 market snapshot</h3>
                {marketResearch.index_snapshot.status === 'available' ? (
                  <>
                    <p className="market-research-meta">
                      End-of-day data as of {marketResearch.index_snapshot.data_as_of}. This is not a live quote.
                    </p>
                    <dl>
                      <dt>Close (points)</dt><dd>{Number(marketResearch.index_snapshot.close).toLocaleString('en-IN')}</dd>
                      <dt>Previous close change</dt><dd>{marketResearch.index_snapshot.previous_close_change_percent == null ? 'Unavailable' : `${marketResearch.index_snapshot.previous_close_change_percent}%`}</dd>
                      <dt>Day range (points)</dt><dd>{Number(marketResearch.index_snapshot.low).toLocaleString('en-IN')} – {Number(marketResearch.index_snapshot.high).toLocaleString('en-IN')}</dd>
                    </dl>
                    <p className="market-research-meta">
                      Source: <a href={marketResearch.index_snapshot.source_url} target="_blank" rel="noreferrer">{marketResearch.index_snapshot.source_name}</a>
                    </p>
                  </>
                ) : (
                  <p className="market-research-notice">NIFTY 50 data is unavailable: {marketResearch.index_snapshot.reason}</p>
                )}
              </div>
            )}
            {marketResearch.profile_fields_needed?.length > 0 && (
              <p className="market-research-notice">
                Add these profile fields first: {marketResearch.profile_fields_needed.join(', ').replaceAll('_', ' ')}.{' '}
                <Link to="/profile">Update profile</Link>
              </p>
            )}
            {marketResearch.market_data_as_of && <p className="market-research-meta">Latest candidate NAV data as of {marketResearch.market_data_as_of}</p>}
            {marketResearch.candidates?.length > 0 ? (
              <ul className="market-candidate-list">
                {marketResearch.candidates.map((candidate) => (
                  <li key={candidate.scheme_code} className="market-candidate">
                    <p className="market-research-meta">{candidate.research_group}</p>
                    <h3>{candidate.scheme_name}</h3>
                    {portfolioContext.schemeCodes.has(Number(candidate.scheme_code)) ? (
                      <p className="candidate-rank">Already in your saved portfolio · <Link to="/investments">View investments</Link></p>
                    ) : portfolioContext.categories.has(String(candidate.scheme_category || '').trim().toLowerCase()) ? (
                      <p className="candidate-rank">You already hold {portfolioContext.categories.get(String(candidate.scheme_category || '').trim().toLowerCase())} fund(s) in this provider-reported category. This is a category check, not a holdings-overlap analysis. <Link to="/investments">View allocation</Link></p>
                    ) : (
                      <p className="market-research-meta"><Link to="/investments">Add your holdings to compare this research with your portfolio</Link></p>
                    )}
                    <p>{candidate.scheme_category}</p>
                    {candidate.relative_rank != null ? (
                      <p className="candidate-rank">
                        Category research rank: <strong>{candidate.relative_rank} of {candidate.peer_count}</strong>
                        {candidate.research_score != null && <> · Comparative score: <strong>{candidate.research_score}/100</strong></>}
                      </p>
                    ) : <p className="market-research-meta">No relative rank: not enough same-category candidates.</p>}
                    <dl>
                      <dt>Latest NAV</dt><dd>₹{candidate.latest_nav} <span>({candidate.nav_date})</span></dd>
                      <dt>1-year NAV return</dt><dd>{candidate.return_1y_percent == null ? 'Unavailable' : `${candidate.return_1y_percent}%`}</dd>
                      <dt>3-year annualized NAV return</dt><dd>{candidate.return_3y_cagr_percent}%</dd>
                      <dt>5-year annualized NAV return</dt><dd>{candidate.return_5y_cagr_percent == null ? 'Unavailable' : `${candidate.return_5y_cagr_percent}%`}</dd>
                      <dt>Positive 1/3/5-year periods</dt><dd>{candidate.periods_available ? `${candidate.positive_periods} of ${candidate.periods_available}` : 'Unavailable'}</dd>
                      <dt>Annualized daily volatility</dt><dd>{candidate.annualized_daily_volatility_percent == null ? 'Unavailable' : `${candidate.annualized_daily_volatility_percent}%`}</dd>
                      <dt>Maximum drawdown, 3 years</dt><dd>{candidate.max_drawdown_3y_percent == null ? 'Unavailable' : `${candidate.max_drawdown_3y_percent}%`}</dd>
                    </dl>
                    {candidate.research_reason && <p className="market-research-meta">{candidate.research_reason}</p>}
                    {candidate.score_basis && candidate.research_score != null && <p className="market-research-meta">Scoring factors: {candidate.score_basis}</p>}
                    <p className="market-research-meta">Source: <a href={candidate.source_url} target="_blank" rel="noreferrer">{candidate.source_name}</a></p>
                  </li>
                ))}
              </ul>
            ) : marketResearch.status === 'no_equity_shortlist' ? (
              <p className="market-research-notice">No equity-fund candidates are shown for the current risk/horizon profile.</p>
            ) : marketResearch.status === 'priority_financial_foundation' ? (
              <p className="market-research-notice">
                Equity research is on hold: {marketResearch.suitability_gate?.detail}{' '}
                Current coverage is {marketResearch.suitability_gate?.emergency_fund_coverage_months} months.
              </p>
            ) : marketResearch.status === 'market_data_unavailable' ? (
              <p className="market-research-notice">No current mutual-fund candidates could be verified, so none are shown.</p>
            ) : marketResearch.status === 'needs_profile' ? (
              <p className="market-research-notice">
                A shortlist needs a complete profile. Fill in the requested fields above, then refresh research.
              </p>
            ) : (
              <p className="market-research-notice">No sufficiently complete candidates were found in the current data.</p>
            )}
            {marketResearch.unavailable_assets?.length > 0 && (
              <div>
                <h3>Coverage gaps and official references</h3>
                <ul>{marketResearch.unavailable_assets.map((item) => <li key={item.asset_class}>{formatCategory(item.asset_class)}: {item.reason}{item.source_url && <> <a href={item.source_url} target="_blank" rel="noreferrer">Official reference</a></>}</li>)}</ul>
              </div>
            )}
            <div className="market-research-notice">
              <strong>How SIP information works:</strong> SIP is a way to invest periodically in an underlying fund, not a separate instrument with its own market price. This screen shows fund NAV history; SIP-specific historical illustrations need an amount and start date and must not be read as forecasts.
            </div>
            {marketResearch.limitations?.length > 0 && (
              <div>
                <h3>Research limits</h3>
                <ul>{marketResearch.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            )}
            {marketResearch.provider && (
              <p className="market-research-meta">
                Data providers: <a href={marketResearch.provider.url} target="_blank" rel="noreferrer">{marketResearch.provider.name} API documentation</a>; primary NAV reference: <a href={marketResearch.provider.primary_data_reference.url} target="_blank" rel="noreferrer">{marketResearch.provider.primary_data_reference.name}</a>.
              </p>
            )}
          </div>
        )}
      </section>

      <div className="recs-actions">
        <button type="button" className="primary" onClick={handleGenerate} disabled={generating}>
          {generating ? 'Checking…' : 'Check for recommendations'}
        </button>
        {hasCandidates && (
          <button type="button" onClick={handleReviewAll} disabled={reviewingAll}>
            {reviewingAll ? 'Reviewing…' : 'Review all pending'}
          </button>
        )}
      </div>

      {genNotice?.type === 'no-data' && (
        <p className="recs-notice">
          {genNotice.message} Add your{' '}
          <Link to="/profile">financial profile</Link> first.
        </p>
      )}
      {genNotice?.type === 'ok' && <p className="recs-notice recs-notice-ok">{genNotice.message}</p>}
      {actionError && <ErrorState error={actionError} />}

      {(!recs || recs.length === 0) && !genNotice && (
        <p className="recs-empty">
          No recommendations yet. Click "Check for recommendations" to run the engine
          against your current financial profile.
        </p>
      )}

      <ul className="recs-list">
        {recs?.map((rec) => {
          const status = displayStatus(rec)
          const isCurrentForProfile = rec.current_for_profile !== false
          const explanation = explanations[rec.id]
          const isExpanded = expandedId === rec.id

          return (
            <li key={rec.id} className={`rec-card ${STATUS_CLASS[status] ?? ''}`}>
              <div className="rec-card-main">
                <div className="rec-card-top">
                  <span className="rec-category">{formatCategory(rec.category)}</span>
                  <span className={`rec-status-pill ${STATUS_CLASS[status] ?? ''}`}>
                    {isCurrentForProfile ? (STATUS_LABEL[status] ?? status) : 'Historical'}
                  </span>
                </div>
                {!isCurrentForProfile && (
                  <p className="recs-notice">
                    This is an older observation from a previous financial profile. It is kept for history and is not triggered by your latest profile.
                  </p>
                )}
                <h3 className="rec-title">{rec.title}</h3>
                <p className="rec-reason">{rec.reason}</p>

                <div className="rec-card-footer">
                  <button type="button" onClick={() => handleToggleExplain(rec.id)}>
                    {isExpanded ? 'Hide details' : 'Why am I seeing this?'}
                  </button>
                  {isCurrentForProfile && rec.state === 'candidate' && (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => handleReviewOne(rec.id)}
                      disabled={reviewingId === rec.id}
                    >
                      {reviewingId === rec.id ? 'Reviewing…' : 'Review'}
                    </button>
                  )}
                  {isCurrentForProfile && ['approved', 'modified'].includes(rec.state) && (
                    <button type="button" className="primary" onClick={() => handlePresent(rec.id)} disabled={lifecycleId === rec.id}>
                      {lifecycleId === rec.id ? 'Presenting…' : 'Present to me'}
                    </button>
                  )}
                  {isCurrentForProfile && rec.state === 'presented' && (
                    <>
                      <button type="button" onClick={() => handleFeedback(rec.id, 'accepted', 'helpful')} disabled={lifecycleId === rec.id}>Accept &amp; helpful</button>
                      <button type="button" onClick={() => handleFeedback(rec.id, 'rejected', 'not_helpful')} disabled={lifecycleId === rec.id}>Reject &amp; not helpful</button>
                      <button type="button" onClick={() => handleFeedback(rec.id, 'rejected', 'harmful')} disabled={lifecycleId === rec.id}>Report harmful</button>
                    </>
                  )}
                  {rec.state === 'evaluated' && <span className="rec-status-pill">Feedback recorded</span>}
                </div>

                {isExpanded && (
                  <div className="rec-explanation">
                    {explanationLoading === rec.id && <LoadingState label="Loading explanation…" />}
                    {explanation?.error && <ErrorState error={explanation.error} />}
                    {explanation && !explanation.error && (
                      <dl>
                        {explanation.user_data_used && (
                          <>
                            <dt>Based on</dt>
                            <dd>
                              {explanation.user_data_used.metric_name?.replaceAll('_', ' ')}:{' '}
                              {explanation.user_data_used.metric_value}
                              {explanation.user_data_used.formula && (
                                <span className="rec-formula"> ({explanation.user_data_used.formula})</span>
                              )}
                            </dd>
                          </>
                        )}
                        {explanation.assumptions?.length > 0 && (
                          <>
                            <dt>Assumptions</dt>
                            <dd>
                              <ul>
                                {explanation.assumptions.map((a, i) => (
                                  <li key={i}>{a}</li>
                                ))}
                              </ul>
                            </dd>
                          </>
                        )}
                        <dt>Confidence</dt>
                        <dd>
                          {explanation.confidence}
                          <span className="rec-confidence-note"> — {explanation.confidence_note}</span>
                        </dd>
                        {explanation.limitations?.length > 0 && (
                          <>
                            <dt>Limitations</dt>
                            <dd>
                              <ul>
                                {explanation.limitations.map((l, i) => (
                                  <li key={i}>{l}</li>
                                ))}
                              </ul>
                            </dd>
                          </>
                        )}
                      </dl>
                    )}
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
