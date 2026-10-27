import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/client'
import { ErrorState } from '../components/ErrorState'

export function Auth() {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const payload = { email, password }
      if (isRegister) {
        payload.full_name = fullName || undefined
        payload.financial_analysis_consent = consent
      }
      await (isRegister ? register(payload) : login(payload))
      navigate('/recommendations')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth-page">
      <h1>{isRegister ? 'Create your account' : 'Sign in'}</h1>
      <p>Your financial profile is private to your account.</p>
      {error && <ErrorState error={error} />}
      <form onSubmit={handleSubmit}>
        {isRegister && (
          <>
            <label>Full name <input autoComplete="name" maxLength={255} value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
            <label><input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} /> I agree to FinGuide+ processing my financial profile for financial analysis.</label>
          </>
        )}
        <label>Email <input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Password <input type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} minLength={isRegister ? 12 : 1} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <button className="primary" type="submit" disabled={busy}>{busy ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}</button>
      </form>
      <button type="button" onClick={() => { setIsRegister((value) => !value); setError(null) }}>
        {isRegister ? 'Already have an account? Sign in' : 'New to FinGuide+? Create an account'}
      </button>
    </section>
  )
}
