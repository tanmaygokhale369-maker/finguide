import { useCallback, useEffect, useMemo, useState } from 'react'
import { createHolding, createHoldingActivity, deleteHolding, deleteHoldingActivity, getFundAnalysis, listHoldingActivity, listHoldings, searchFundSchemes, updateHolding } from '../api/client'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import './AppPages.css'

const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })

export function Investments() {
  const [holdings, setHoldings] = useState(null)
  const [query, setQuery] = useState('')
  const [schemes, setSchemes] = useState([])
  const [selected, setSelected] = useState(null)
  const [units, setUnits] = useState('')
  const [invested, setInvested] = useState('')
  const [sip, setSip] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({ units: '', amount_invested: '', monthly_sip: '' })
  const [activityLists, setActivityLists] = useState({})
  const [activityForm, setActivityForm] = useState({ activity_type: 'purchase', units: '', amount: '', activity_date: new Date().toISOString().slice(0, 10), note: '' })
  const [fundAnalyses, setFundAnalyses] = useState({})
  const [researchQuery, setResearchQuery] = useState('')
  const [researchSchemes, setResearchSchemes] = useState([])
  const [researchSelected, setResearchSelected] = useState(null)
  const [researchAnalysis, setResearchAnalysis] = useState(null)
  const [researchBusy, setResearchBusy] = useState(false)
  const [researchError, setResearchError] = useState(null)

  const portfolio = useMemo(() => {
    const priced = (holdings || []).filter((item) => item.valuation_status === 'available' && item.current_value != null)
    const total = priced.reduce((sum, item) => sum + Number(item.current_value), 0)
    const costTracked = priced.filter((item) => Number(item.amount_invested) > 0)
    const trackedCost = costTracked.reduce((sum, item) => sum + Number(item.amount_invested), 0)
    const trackedValue = costTracked.reduce((sum, item) => sum + Number(item.current_value) + Number(item.redemption_proceeds || 0), 0)
    const groups = new Map()
    for (const item of priced) {
      const category = item.scheme_category || 'Category unavailable'
      groups.set(category, (groups.get(category) || 0) + Number(item.current_value))
    }
    return {
      total,
      pricedCount: priced.length,
      unavailableCount: (holdings || []).length - priced.length,
      monthlySip: (holdings || []).reduce((sum, item) => sum + Number(item.monthly_sip || 0), 0),
      invested: (holdings || []).reduce((sum, item) => sum + Number(item.amount_invested || 0), 0),
      trackedCost,
      trackedValue,
      recordedGainLoss: trackedValue - trackedCost,
      recordedGainLossPercent: trackedCost > 0 ? ((trackedValue / trackedCost) - 1) * 100 : null,
      groups: [...groups.entries()].sort((a, b) => b[1] - a[1]),
    }
  }, [holdings])

  const refresh = useCallback(async () => {
    setHoldings(await listHoldings())
  }, [])

  useEffect(() => {
    refresh().catch(setError)
  }, [refresh])

  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setSchemes([])
      return undefined
    }
    let live = true
    const timer = setTimeout(() => searchFundSchemes(query.trim()).then((items) => live && setSchemes(items)).catch((err) => live && setError(err)), 300)
    return () => { live = false; clearTimeout(timer) }
  }, [query, selected])

  useEffect(() => {
    if (researchSelected || researchQuery.trim().length < 2) {
      setResearchSchemes([])
      return undefined
    }
    let live = true
    const timer = setTimeout(() => searchFundSchemes(researchQuery.trim()).then((items) => live && setResearchSchemes(items)).catch((err) => live && setResearchError(err)), 300)
    return () => { live = false; clearTimeout(timer) }
  }, [researchQuery, researchSelected])

  async function analyzeResearchFund(event) {
    event.preventDefault()
    if (!researchSelected) return
    setResearchBusy(true)
    setResearchError(null)
    setResearchAnalysis(null)
    try { setResearchAnalysis(await getFundAnalysis(researchSelected.scheme_code)) }
    catch (err) { setResearchError(err) }
    finally { setResearchBusy(false) }
  }

  async function addHolding(event) {
    event.preventDefault()
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      await createHolding({ scheme_code: selected.scheme_code, units, amount_invested: invested || null, monthly_sip: sip || null })
      setSelected(null); setQuery(''); setUnits(''); setInvested(''); setSip('')
      setNotice('Holding saved. Its value uses the latest available NAV, when the free data feed responds.')
      await refresh()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  async function remove(id) {
    if (!window.confirm('Remove this holding from your saved portfolio?')) return
    setError(null)
    try {
      await deleteHolding(id)
      setNotice('Holding removed from your saved portfolio.')
      await refresh()
    } catch (err) {
      // The server may already have removed a row while this page still
      // displayed a stale copy. Refresh instead of leaving a dead entry.
      if (err?.status === 404) {
        try { await refresh(); setNotice('Your saved portfolio was refreshed; that holding was already removed.') }
        catch (refreshError) { setError(refreshError) }
      } else setError(err)
    }
  }

  function beginEdit(item) {
    setEditingId(item.id)
    setEditForm({ units: String(item.units), amount_invested: item.amount_invested ?? '', monthly_sip: item.monthly_sip ?? '' })
    setError(null)
  }

  async function saveEdit(event, id) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await updateHolding(id, {
        units: editForm.units,
        amount_invested: editForm.amount_invested === '' ? null : editForm.amount_invested,
        monthly_sip: editForm.monthly_sip === '' ? null : editForm.monthly_sip,
      })
      setEditingId(null)
      setNotice('Holding details updated.')
      await refresh()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  async function loadActivity(id) {
    if (activityLists[id]) {
      setActivityLists((current) => ({ ...current, [id]: null }))
      return
    }
    try {
      const events = await listHoldingActivity(id)
      setActivityLists((current) => ({ ...current, [id]: events }))
    }
    catch (err) { setError(err) }
  }

  async function saveActivity(event, id) {
    event.preventDefault()
    setBusy(true); setError(null)
    try {
      await createHoldingActivity(id, {
        ...activityForm,
        units: activityForm.units,
        amount: activityForm.activity_type === 'adjustment' ? null : activityForm.amount,
        note: activityForm.note || null,
      })
      setActivityForm({ ...activityForm, units: '', amount: '', note: '' })
      setActivityLists((current) => ({ ...current, [id]: null }))
      const events = await listHoldingActivity(id)
      setActivityLists((current) => ({ ...current, [id]: events }))
      setNotice('Activity recorded and holding units updated.')
      await refresh()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  async function removeActivity(holdingId, activityId) {
    if (!window.confirm('Delete this activity and reverse its effect on the saved units?')) return
    try {
      await deleteHoldingActivity(holdingId, activityId)
      const events = await listHoldingActivity(holdingId)
      setActivityLists((current) => ({ ...current, [holdingId]: events }))
      await refresh()
      setNotice('Activity deleted and saved units reconciled.')
    } catch (err) { setError(err) }
  }

  async function loadFundAnalysis(holding) {
    if (fundAnalyses[holding.id]?.data) {
      setFundAnalyses((current) => ({ ...current, [holding.id]: null }))
      return
    }
    setFundAnalyses((current) => ({ ...current, [holding.id]: { loading: true } }))
    try {
      const data = await getFundAnalysis(holding.scheme_code)
      setFundAnalyses((current) => ({ ...current, [holding.id]: { data } }))
    } catch (err) {
      setFundAnalyses((current) => ({ ...current, [holding.id]: { error: err } }))
    }
  }

  return (
    <section className="app-page">
      <header className="page-heading"><div><p className="eyebrow">YOUR PORTFOLIO</p><h1>Investments</h1><p className="muted">Record your mutual-fund units and SIP contributions. FinGuide fetches NAV data when available to estimate current value.</p></div></header>
      <section className="panel fund-research-panel">
        <div className="panel-heading"><div><h2>Research a mutual fund</h2><p className="muted">Check the published expense ratio and compare historical returns with NIFTY 50 TRI. This search does not add anything to your portfolio.</p></div></div>
        <form className="fund-research-form" onSubmit={analyzeResearchFund}>
          <label>Find a scheme<input value={researchSelected ? researchSelected.scheme_name : researchQuery} onChange={(event) => { setResearchSelected(null); setResearchAnalysis(null); setResearchError(null); setResearchQuery(event.target.value) }} placeholder="Search any mutual fund" /></label>
          {!researchSelected && researchSchemes.length > 0 && <ul className="scheme-search-results">{researchSchemes.map((item) => <li key={item.scheme_code}><button type="button" onClick={() => { setResearchSelected(item); setResearchQuery(item.scheme_name); setResearchSchemes([]) }}>{item.scheme_name}</button></li>)}</ul>}
          <button className="primary" type="submit" disabled={!researchSelected || researchBusy}>{researchBusy ? 'Analyzing…' : 'Analyze fund'}</button>
        </form>
        {researchError && <ErrorState error={researchError} />}
        {researchAnalysis && <div className="holding-activity standalone-fund-analysis">
          <h3>{researchSelected.scheme_name}</h3>
          <p><strong>Fund NAV:</strong> {researchAnalysis.nav_status === 'available' ? `Recent (${researchAnalysis.nav_data_as_of})` : `Stale (${researchAnalysis.nav_data_as_of}; ${researchAnalysis.nav_age_days} days old)`}</p>
          <p><strong>Total expense ratio:</strong> {researchAnalysis.expense_ratio.status === 'available' ? `${researchAnalysis.expense_ratio.ter_percent}% (Direct) as of ${researchAnalysis.expense_ratio.data_as_of}` : researchAnalysis.expense_ratio.status === 'stale' ? `Latest reported ${researchAnalysis.expense_ratio.latest_reported_ter_percent}% is stale (as of ${researchAnalysis.expense_ratio.data_as_of}); not treated as current.` : researchAnalysis.expense_ratio.reason}</p>
          {researchAnalysis.expense_ratio.status !== 'unavailable' && <p className="market-research-meta">TER components (percentage points): base {researchAnalysis.expense_ratio.base_expense_ratio_percent ?? '—'}, brokerage {researchAnalysis.expense_ratio.brokerage_cost_percent ?? '—'}, transaction {researchAnalysis.expense_ratio.transaction_cost_percent ?? '—'}, levies {researchAnalysis.expense_ratio.statutory_levies_percent ?? '—'}. <a href={researchAnalysis.expense_ratio.source_url} target="_blank" rel="noreferrer">AMFI source</a></p>}
          <h4>Matched benchmark</h4>
          {researchAnalysis.benchmark.status === 'available' ? <><p>{researchAnalysis.benchmark.name}, data as of {researchAnalysis.benchmark.data_as_of}</p><div className="benchmark-table-wrap"><table className="benchmark-table"><thead><tr><th>Period</th><th>Fund return</th><th>NIFTY 50 TRI return</th><th>Difference</th></tr></thead><tbody>{['1y', '3y', '5y'].map((period) => { const row = researchAnalysis.benchmark.comparisons[period]; return <tr key={period}><td>{period}</td><td>{row.fund_return_percent == null ? 'Unavailable' : `${row.fund_return_percent}%`}</td><td>{row.benchmark_return_percent == null ? 'Unavailable' : `${row.benchmark_return_percent}%`}</td><td>{row.difference_percentage_points == null ? 'Unavailable' : `${row.difference_percentage_points} pp`}</td></tr> })}</tbody></table></div><p className="market-research-meta">{researchAnalysis.benchmark.method_note} <a href={researchAnalysis.benchmark.source_url} target="_blank" rel="noreferrer">NSE Indices source</a></p></> : <p>{researchAnalysis.benchmark.reason}</p>}
          <p className="fine-print">{researchAnalysis.analysis_notice} Historical returns are not forecasts or expected returns. TER is not deducted again from NAV returns.</p>
        </div>}
      </section>
      <div className="dashboard-columns transactions-layout">
        <section className="panel">
          <h2>Add a mutual-fund holding</h2>
          <form className="app-form" onSubmit={addHolding}>
            <label>Find a scheme<input value={selected ? selected.scheme_name : query} onChange={(e) => { setSelected(null); setQuery(e.target.value) }} placeholder="Search fund name" required /></label>
            {!selected && schemes.length > 0 && <ul className="scheme-search-results">{schemes.map((item) => <li key={item.scheme_code}><button type="button" onClick={() => { setSelected(item); setQuery(item.scheme_name); setSchemes([]) }}>{item.scheme_name}</button></li>)}</ul>}
            <label>Units you own<input type="number" min="0.000001" step="0.000001" value={units} onChange={(e) => setUnits(e.target.value)} required /></label>
            <label>Total amount invested (optional, ₹)<input type="number" min="0" step="0.01" value={invested} onChange={(e) => setInvested(e.target.value)} /></label>
            <label>Monthly SIP contribution (optional, ₹)<input type="number" min="0" step="0.01" value={sip} onChange={(e) => setSip(e.target.value)} /></label>
            <button className="primary" disabled={busy || !selected}>{busy ? 'Saving…' : 'Save holding'}</button>
          </form>
          <p className="fine-print">Units and investment totals are entered by you. A NAV-derived value is an estimate, not a broker balance. This page does not connect to a demat account or CAMS/KFintech statement.</p>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><h2>Saved mutual funds</h2><p className="muted">Personal portfolio records, scoped to your signed-in account.</p></div><button type="button" onClick={() => refresh().catch(setError)}>Refresh NAVs</button></div>
          {error && <ErrorState error={error} />}
          {notice && <p className="inline-notice">{notice}</p>}
          {holdings === null ? <LoadingState label="Loading holdings…" /> : holdings.length === 0 ? <p className="empty-state">No holdings saved yet. Search a scheme to add your first fund.</p> : (
            <>
              <div className="metric-grid holdings-metrics">
                <div className="metric-card"><span>Verified NAV value</span><strong>{INR.format(portfolio.total)}</strong></div>
                <div className="metric-card"><span>Monthly SIPs entered</span><strong>{INR.format(portfolio.monthlySip)}</strong></div>
                <div className="metric-card"><span>Invested amount entered</span><strong>{INR.format(portfolio.invested)}</strong></div>
                <div className="metric-card"><span>Valuations available</span><strong>{portfolio.pricedCount} / {holdings.length}</strong></div>
              </div>
              <div className={`callout ${portfolio.recordedGainLoss >= 0 ? '' : 'portfolio-loss'}`}>
                <strong>Value change across holdings with complete recorded contributions</strong>
                {portfolio.trackedCost > 0 ? <p>{INR.format(portfolio.recordedGainLoss)} ({portfolio.recordedGainLossPercent.toFixed(2)}%) across {holdings.filter((item) => item.valuation_status === 'available' && Number(item.amount_invested) > 0).length} valued holding(s), including recorded redemption proceeds.</p> : <p>Enter the total invested amount for a holding to compare it with its NAV-based current value.</p>}
              </div>
              <h3>Category allocation by verified NAV value</h3>
              {portfolio.groups.length ? <ul className="simple-list holdings-allocation">{portfolio.groups.map(([category, value]) => <li key={category}><span>{category}</span><strong>{INR.format(value)} · {portfolio.total ? `${(value / portfolio.total * 100).toFixed(1)}%` : '—'}</strong></li>)}</ul> : <p className="empty-state">No current NAV values are available to calculate category allocation.</p>}
              {portfolio.unavailableCount > 0 && <p className="market-research-notice">{portfolio.unavailableCount} holding(s) are excluded from category allocation because a recent NAV was unavailable.</p>}
              <ul className="simple-list holdings-list">{holdings.map((item) => <li key={item.id}><div><strong>{item.scheme_name}</strong><small>{item.scheme_category || 'Scheme category unavailable'} · Code {item.scheme_code} · {Number(item.units).toLocaleString('en-IN', { maximumFractionDigits: 6 })} units{item.monthly_sip != null ? ` · SIP ${INR.format(Number(item.monthly_sip))}/month` : ''}</small><small>{item.valuation_status === 'available' ? `Estimated value ${INR.format(Number(item.current_value))} · NAV ${item.current_nav} as of ${item.nav_date}` : 'Current valuation unavailable: latest NAV could not be verified.'}{item.amount_invested != null ? ` · Entered invested amount ${INR.format(Number(item.amount_invested))}` : ''}{item.valuation_status === 'available' && Number(item.amount_invested) > 0 ? ` · Change including redemption proceeds ${INR.format(Number(item.current_value) + Number(item.redemption_proceeds || 0) - Number(item.amount_invested))}` : ''}</small>
                <button className="activity-toggle" type="button" onClick={() => loadFundAnalysis(item)}>{fundAnalyses[item.id]?.data ? 'Hide fund analysis' : fundAnalyses[item.id]?.loading ? 'Loading analysis…' : 'Analyze TER & benchmark'}</button>
                {fundAnalyses[item.id]?.error && <p className="market-research-notice">Fund analysis is unavailable right now: {fundAnalyses[item.id].error.message}</p>}
                {fundAnalyses[item.id]?.data && <div className="holding-activity"><h4>Fund cost and benchmark analysis</h4><p><strong>Fund NAV:</strong> {fundAnalyses[item.id].data.nav_status === 'available' ? `Recent (${fundAnalyses[item.id].data.nav_data_as_of})` : `Stale (${fundAnalyses[item.id].data.nav_data_as_of}; ${fundAnalyses[item.id].data.nav_age_days} days old)`}</p><p><strong>Total expense ratio:</strong> {fundAnalyses[item.id].data.expense_ratio.status === 'available' ? `${fundAnalyses[item.id].data.expense_ratio.ter_percent}% (Direct) as of ${fundAnalyses[item.id].data.expense_ratio.data_as_of}` : fundAnalyses[item.id].data.expense_ratio.status === 'stale' ? `Latest reported ${fundAnalyses[item.id].data.expense_ratio.latest_reported_ter_percent}% is stale (as of ${fundAnalyses[item.id].data.expense_ratio.data_as_of}); not treated as current.` : fundAnalyses[item.id].data.expense_ratio.reason}</p>{fundAnalyses[item.id].data.expense_ratio.status !== 'unavailable' && <p className="market-research-meta">TER components (percentage points): base {fundAnalyses[item.id].data.expense_ratio.base_expense_ratio_percent ?? '—'}, brokerage {fundAnalyses[item.id].data.expense_ratio.brokerage_cost_percent ?? '—'}, transaction {fundAnalyses[item.id].data.expense_ratio.transaction_cost_percent ?? '—'}, levies {fundAnalyses[item.id].data.expense_ratio.statutory_levies_percent ?? '—'}. <a href={fundAnalyses[item.id].data.expense_ratio.source_url} target="_blank" rel="noreferrer">AMFI source</a></p>}<h4>Matched benchmark</h4>{fundAnalyses[item.id].data.benchmark.status === 'available' ? <><p>{fundAnalyses[item.id].data.benchmark.name}, data as of {fundAnalyses[item.id].data.benchmark.data_as_of}</p><div className="benchmark-table-wrap"><table className="benchmark-table"><thead><tr><th>Period</th><th>Fund return</th><th>NIFTY 50 TRI return</th><th>Difference</th></tr></thead><tbody>{['1y', '3y', '5y'].map((period) => { const row = fundAnalyses[item.id].data.benchmark.comparisons[period]; return <tr key={period}><td>{period}</td><td>{row.fund_return_percent == null ? 'Unavailable' : `${row.fund_return_percent}%`}</td><td>{row.benchmark_return_percent == null ? 'Unavailable' : `${row.benchmark_return_percent}%`}</td><td>{row.difference_percentage_points == null ? 'Unavailable' : `${row.difference_percentage_points} pp`}</td></tr> })}</tbody></table></div><p className="market-research-meta">{fundAnalyses[item.id].data.benchmark.method_note} <a href={fundAnalyses[item.id].data.benchmark.source_url} target="_blank" rel="noreferrer">NSE Indices source</a></p></> : <p>{fundAnalyses[item.id].data.benchmark.reason}</p>}<p className="fine-print">{fundAnalyses[item.id].data.analysis_notice} TER is a published cost ratio and is not deducted again from NAV returns.</p></div>}
                {editingId === item.id && <form className="holding-edit-form" onSubmit={(event) => saveEdit(event, item.id)}><label>Units<input required type="number" min="0.000001" step="0.000001" value={editForm.units} onChange={(event) => setEditForm({ ...editForm, units: event.target.value })} /></label><label>Invested (₹)<input type="number" min="0" step="0.01" value={editForm.amount_invested} onChange={(event) => setEditForm({ ...editForm, amount_invested: event.target.value })} /></label><label>Monthly SIP (₹)<input type="number" min="0" step="0.01" value={editForm.monthly_sip} onChange={(event) => setEditForm({ ...editForm, monthly_sip: event.target.value })} /></label><div><button className="primary" disabled={busy} type="submit">{busy ? 'Saving…' : 'Save changes'}</button> <button type="button" onClick={() => setEditingId(null)}>Cancel</button></div></form>}
                <button className="activity-toggle" type="button" onClick={() => loadActivity(item.id)}>{activityLists[item.id] ? 'Hide activity' : `Activity (${item.activity_count})`}</button>
                {activityLists[item.id] && <div className="holding-activity"><h4>Transaction history</h4><form className="holding-edit-form" onSubmit={(event) => saveActivity(event, item.id)}><label>Type<select value={activityForm.activity_type} onChange={(event) => setActivityForm({ ...activityForm, activity_type: event.target.value })}><option value="purchase">Purchase / SIP instalment</option><option value="redemption">Redemption</option><option value="adjustment">Unit adjustment</option></select></label><label>{activityForm.activity_type === 'adjustment' ? 'Signed unit change' : 'Units'}<input required type="number" step="0.000001" min={activityForm.activity_type === 'adjustment' ? undefined : '0.000001'} value={activityForm.units} onChange={(event) => setActivityForm({ ...activityForm, units: event.target.value })} /></label>{activityForm.activity_type !== 'adjustment' && <label>{activityForm.activity_type === 'purchase' ? 'Amount invested (₹)' : 'Redemption proceeds (₹)'}<input required type="number" min="0.01" step="0.01" value={activityForm.amount} onChange={(event) => setActivityForm({ ...activityForm, amount: event.target.value })} /></label>}<label>Date<input required type="date" max={new Date().toISOString().slice(0, 10)} value={activityForm.activity_date} onChange={(event) => setActivityForm({ ...activityForm, activity_date: event.target.value })} /></label><label>Note (optional)<input maxLength="500" value={activityForm.note} onChange={(event) => setActivityForm({ ...activityForm, note: event.target.value })} /></label><div><button className="primary" disabled={busy} type="submit">Record activity</button></div></form><ul className="simple-list">{activityLists[item.id].map((activity) => <li key={activity.id}><div><strong>{activity.activity_type.replaceAll('_', ' ')}</strong><small>{activity.activity_date} · {activity.units_delta > 0 ? '+' : ''}{activity.units_delta} units{activity.amount != null ? ` · ₹${activity.amount}` : ''}{activity.note ? ` · ${activity.note}` : ''}</small></div>{activity.activity_type !== 'opening_balance' && <button className="text-button" type="button" onClick={() => removeActivity(item.id, activity.id)}>Delete</button>}</li>)}</ul></div>}
              </div><div className="holding-actions">{editingId !== item.id && <button type="button" onClick={() => beginEdit(item)}>Edit</button>}<button className="text-button" type="button" onClick={() => remove(item.id)}>Remove</button></div></li>)}</ul>
            </>
          )}
        </section>
      </div>
      <p className="fine-print">Activity records are manual and do not come from a broker statement. Purchase entries increase units and recorded contributions; redemptions reduce units and are included in the cumulative value comparison. The cumulative percentage is not annualized, time-weighted, or an SIP return; it excludes tax and fees. Category percentages use only holdings with a recent NAV. Latest NAV source: MFapi.in, an unofficial transport for scheme NAV history; verify on the AMC or AMFI.</p>
    </section>
  )
}
