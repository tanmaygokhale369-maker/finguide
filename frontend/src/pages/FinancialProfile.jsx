import { useEffect, useState } from 'react'
import {
  ApiError,
  createProfile,
  getProfile,
  getProfileMetrics,
  updateProfile,
} from '../api/client'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import './FinancialProfile.css'

const EMPTY_FORM = {
  monthly_income: '',
  fixed_expenses: '',
  variable_expenses: '',
  savings: '',
  debt: '',
  emergency_fund_amount: '',
  dependents: '',
  has_insurance: null,
  existing_investments_amount: '',
  risk_preference: '',
  investment_horizon_years: '',
  financial_goals: '',
}

const AMOUNT_FIELDS = [
  ['monthly_income', 'Monthly income'],
  ['fixed_expenses', 'Fixed expenses (rent, EMIs, etc.)'],
  ['variable_expenses', 'Variable expenses (groceries, discretionary, etc.)'],
  ['savings', 'Current savings'],
  ['debt', 'Total debt balance'],
  ['emergency_fund_amount', 'Emergency fund amount'],
  ['existing_investments_amount', 'Existing investments'],
]

// A field left blank is sent as omitted, not zero — the backend's own
// rule (Brick 05: "missing debt ≠ ₹0 debt"). Converting '' to undefined
// here is what makes that distinction survive the round trip.
function toPayloadValue(raw) {
  if (raw === '' || raw === null || raw === undefined) return undefined
  return raw
}

function profileToForm(profile) {
  const form = { ...EMPTY_FORM }
  for (const key of Object.keys(EMPTY_FORM)) {
    const value = profile[key]
    if (value === null || value === undefined) continue
    form[key] = typeof value === 'boolean' ? value : String(value)
  }
  return form
}

export function FinancialProfile() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [exists, setExists] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [savedAt, setSavedAt] = useState(null)
  const profileFieldsCount = Object.keys(EMPTY_FORM).length
  const completedProfileFields = Object.values(form).filter((value) => value !== '' && value !== null && value !== undefined).length
  const profileCompletion = Math.round((completedProfileFields / profileFieldsCount) * 100)

  useEffect(() => {
    let cancelled = false
    getProfile()
      .then((profile) => {
        if (cancelled) return
        setForm(profileToForm(profile))
        setExists(true)
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          // No profile yet — the empty form is the correct state, not an error.
          setExists(false)
        } else {
          setLoadError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function handleChange(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSavedAt(null)

    const payload = {}
    for (const key of Object.keys(EMPTY_FORM)) {
      const value = toPayloadValue(form[key])
      if (value !== undefined) payload[key] = value
    }

    try {
      const saved = exists ? await updateProfile(payload) : await createProfile(payload)
      setForm(profileToForm(saved))
      setExists(true)
      setSavedAt(new Date())
      // Recompute derived metrics immediately so the page shows what the
      // recommendation engine will actually see — not a stale snapshot.
      const freshMetrics = await getProfileMetrics()
      setMetrics(freshMetrics)
    } catch (err) {
      setSaveError(err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState label="Loading your financial profile…" />
  if (loadError) return <ErrorState error={loadError} onRetry={() => window.location.reload()} />

  return (
    <section className="profile-page">
      <div className="profile-heading">
        <div><p className="eyebrow">YOUR FINANCIAL BASELINE</p><h1>Financial Profile</h1></div>
        <p className="profile-intro">
          This is what FinGuide+ uses to compute your financial ratios and generate
          recommendations. Leave anything you're not sure about blank — a blank field
          is treated as unknown, never as zero.
        </p>
      </div>

      <div className="profile-layout">
      <div className="profile-primary">
      <form onSubmit={handleSubmit} className="profile-form">
        <div className="field-grid">
          {AMOUNT_FIELDS.map(([field, label]) => (
            <label key={field} className="field">
              <span>{label}</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={form[field]}
                onChange={(e) => handleChange(field, e.target.value)}
                placeholder="Not provided"
              />
            </label>
          ))}

          <label className="field">
            <span>Dependents</span>
            <input
              type="number"
              min="0"
              step="1"
              value={form.dependents}
              onChange={(e) => handleChange('dependents', e.target.value)}
              placeholder="Not provided"
            />
          </label>

          <label className="field">
            <span>Investment horizon (years)</span>
            <input
              type="number"
              min="0"
              step="1"
              value={form.investment_horizon_years}
              onChange={(e) => handleChange('investment_horizon_years', e.target.value)}
              placeholder="Not provided"
            />
          </label>

          <label className="field">
            <span>Risk preference</span>
            <select
              value={form.risk_preference}
              onChange={(e) => handleChange('risk_preference', e.target.value)}
            >
              <option value="">Not provided</option>
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </label>

          <label className="field">
            <span>Has insurance?</span>
            <select
              value={form.has_insurance === null ? '' : String(form.has_insurance)}
              onChange={(e) =>
                handleChange('has_insurance', e.target.value === '' ? null : e.target.value === 'true')
              }
            >
              <option value="">Not provided</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
        </div>

        <label className="field field-wide">
          <span>Financial goals</span>
          <textarea
            rows={3}
            value={form.financial_goals}
            onChange={(e) => handleChange('financial_goals', e.target.value)}
            placeholder="Not provided"
          />
        </label>

        {saveError && <ErrorState error={saveError} />}

        <div className="form-actions">
          <button type="submit" className="primary" disabled={saving}>
            {saving ? 'Saving…' : exists ? 'Save changes' : 'Create profile'}
          </button>
          {savedAt && <span className="saved-note">Saved and metrics recomputed.</span>}
        </div>
      </form>

      {metrics && (
        <div className="metrics-summary">
          <h2>Current ratios</h2>
          <ul>
            {metrics.map((m) => (
              <li key={m.metric_name}>
                <span className="metric-name">{m.metric_name.replaceAll('_', ' ')}</span>
                <span className="metric-value">
                  {m.status === 'COMPUTED' ? m.value : m.status.toLowerCase().replaceAll('_', ' ')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      </div>

      <aside className="profile-rail">
        <section className="panel profile-progress-panel">
          <p className="eyebrow">PROFILE COVERAGE</p>
          <h2>{completedProfileFields} of {profileFieldsCount} details provided</h2>
          <div className="profile-progress-track" role="progressbar" aria-label="Profile details provided" aria-valuemin={0} aria-valuemax={profileFieldsCount} aria-valuenow={completedProfileFields}>
            <span style={{ width: `${profileCompletion}%` }} />
          </div>
          <p className="muted">More complete information can make FinGuide’s calculations and fund research screens more relevant. Missing values stay unknown; FinGuide does not fill them in for you.</p>
        </section>

        <section className="panel profile-guide-panel">
          <p className="eyebrow">HOW IT IS USED</p>
          <h2>What these details support</h2>
          <ul>
            <li><strong>Income and expenses</strong><span>Cash-flow and savings-capacity calculations.</span></li>
            <li><strong>Savings, debt, and emergency fund</strong><span>Financial resilience observations.</span></li>
            <li><strong>Risk preference and horizon</strong><span>Suitability gates for market research shortlists.</span></li>
            <li><strong>Goals and dependents</strong><span>Context for planning and protection needs.</span></li>
          </ul>
          <p className="fine-print">Only the information you enter is used here. Your profile is not sent to Gemini for chat responses.</p>
        </section>
      </aside>
      </div>
    </section>
  )
}
