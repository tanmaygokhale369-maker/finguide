import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { exportUserData, getChatCapabilities, logout, recordConsent } from '../api/client'
import { ErrorState } from '../components/ErrorState'
import './AppPages.css'

export function Settings() {
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)
  const [newsChoice, setNewsChoice] = useState('')
  const [analyticsChoice, setAnalyticsChoice] = useState('')
  const [aiChoice, setAiChoice] = useState('')
  const [aiPolicyVersion, setAiPolicyVersion] = useState('1.2-ai-gemini')
  const [aiProvider, setAiProvider] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getChatCapabilities().then((capabilities) => {
      setAiProvider(capabilities.provider)
      if (capabilities.consent_policy_version) setAiPolicyVersion(capabilities.consent_policy_version)
    }).catch(() => {})
  }, [])

  async function downloadExport() {
    setBusy(true); setError(null); setNotice(null)
    try {
      const data = await exportUserData()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `finguide-data-${new Date().toISOString().slice(0, 10)}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      setNotice('Your data export was downloaded.')
    } catch (err) { setError(err) }
    finally { setBusy(false) }
  }

  async function saveConsent() {
    const choices = [
      newsChoice && { purpose: 'external_news_analysis', granted: newsChoice === 'yes', policy_version: '1.1' },
      analyticsChoice && { purpose: 'product_analytics', granted: analyticsChoice === 'yes', policy_version: '1.1' },
      aiChoice && { purpose: 'ai_conversation_processing', granted: aiChoice === 'yes', policy_version: aiPolicyVersion },
    ].filter(Boolean)
    if (!choices.length) { setNotice('Choose a preference first.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      await Promise.all(choices.map((choice) => recordConsent(choice)))
      setNotice('Your consent choices were recorded.')
      setNewsChoice(''); setAnalyticsChoice(''); setAiChoice('')
    } catch (err) { setError(err) }
    finally { setBusy(false) }
  }

  async function signOut() {
    setBusy(true); setError(null)
    try { await logout(); navigate('/auth') }
    catch (err) { setError(err) }
    finally { setBusy(false) }
  }

  return (
    <section className="app-page settings-page">
      <div className="page-heading"><div><p className="eyebrow">CONTROL YOUR DATA</p><h1>Privacy & settings</h1><p className="muted">Export your FinGuide+ data or update optional analysis preferences.</p></div></div>
      {error && <ErrorState error={error} />}{notice && <p className="inline-notice" role="status">{notice}</p>}
      <div className="settings-grid">
        <section className="panel"><h2>Download your data</h2><p>Save a JSON copy of your profile, transactions, recommendations, conversations, and available records.</p><button className="primary" type="button" disabled={busy} onClick={downloadExport}>{busy ? 'Working…' : 'Download data export'}</button></section>
        <section className="panel"><h2>Optional analysis preferences</h2><p>Record whether FinGuide+ may use external AI conversation processing, news analysis, or product analytics. These preferences do not enable services that are not configured.</p>
          <label className="consent-choice">AI conversation processing<select value={aiChoice} onChange={(event) => setAiChoice(event.target.value)}><option value="">Choose a preference…</option><option value="yes">Allow chat messages to be sent to the configured AI provider</option><option value="no">Do not allow</option></select></label>
          <p className="fine-print">{aiProvider === 'Gemini' ? 'Current-market questions send the latest question plus selected public NIFTY 50 data or RBI/SEBI headline snippets when relevant; earlier chat turns and your saved profile are excluded. Google may retain the query, public market context, and output for up to 30 days. Grounding may incur charges depending on your project and quota. Gemini unpaid quota may be reviewed by people and used to improve Google products.' : 'Chat messages and bounded conversation history are sent to the configured provider only after you allow it.'} Your saved profile is not sent.</p>
          <label className="consent-choice">External news analysis<select value={newsChoice} onChange={(event) => setNewsChoice(event.target.value)}><option value="">Choose a preference…</option><option value="yes">Allow</option><option value="no">Do not allow</option></select></label>
          <label className="consent-choice">Product analytics<select value={analyticsChoice} onChange={(event) => setAnalyticsChoice(event.target.value)}><option value="">Choose a preference…</option><option value="yes">Allow</option><option value="no">Do not allow</option></select></label>
          <button type="button" disabled={busy} onClick={saveConsent}>Save selected preferences</button>
        </section>
        <section className="panel"><h2>Account session</h2><p>Sign out of the current browser session. In local development the app may use a development identity instead of a registered account.</p><button type="button" disabled={busy} onClick={signOut}>Sign out</button></section>
        <section className="panel"><h2>About this build</h2><p>Transactions are manual entries. External evidence is marked unverified, and recommendations are deterministic rules based on your saved profile.</p><p className="fine-print">No bank connection, external news provider, or financial product execution is configured.</p></section>
      </div>
    </section>
  )
}
