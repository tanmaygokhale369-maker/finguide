import { useCallback, useEffect, useState } from 'react'
import { createTransaction, deleteTransaction, listTransactions } from '../api/client'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import './AppPages.css'

const INCOME_CATEGORIES = ['salary', 'business_income', 'investment_income', 'rental_income', 'gift_received', 'refund', 'other_income']
const EXPENSE_CATEGORIES = ['housing', 'utilities', 'groceries', 'transportation', 'healthcare', 'insurance', 'debt_payment', 'dining_out', 'entertainment', 'shopping', 'education', 'personal_care', 'subscriptions', 'travel', 'other_expense', 'uncategorized']
const today = new Date().toISOString().slice(0, 10)
const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })
const label = (value) => value.replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase())
const emptyForm = { amount: '', type: 'expense', category: 'groceries', transaction_date: today, description: '' }

export function Transactions() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setRows(await listTransactions({ limit: 200 })) }
    catch (err) { setError(err) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    let cancelled = false
    listTransactions({ limit: 200 })
      .then((result) => { if (!cancelled) setRows(result) })
      .catch((err) => { if (!cancelled) setError(err) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  function changeType(type) {
    const categories = type === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES
    setForm((current) => ({ ...current, type, category: categories[0] }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setNotice(null)
    try {
      await createTransaction({ ...form, amount: Number(form.amount), description: form.description.trim() || null })
      setForm({ ...emptyForm, transaction_date: today })
      setNotice('Transaction saved.')
      await refresh()
    } catch (err) { setNotice(err.message) }
    finally { setSaving(false) }
  }

  async function remove(row) {
    if (!window.confirm(`Delete this ${row.type} transaction for ${money.format(Number(row.amount))}?`)) return
    try {
      await deleteTransaction(row.id)
      setRows((current) => current.filter((item) => item.id !== row.id))
      setNotice('Transaction deleted.')
    } catch (err) { setNotice(err.message) }
  }

  const categories = form.type === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES
  return (
    <section className="app-page">
      <div className="page-heading"><div><p className="eyebrow">CASH FLOW</p><h1>Transactions</h1><p className="muted">Record income and expenses to build a useful spending history.</p></div></div>
      <div className="dashboard-columns transactions-layout">
        <section className="panel">
          <h2>Add transaction</h2>
          <form className="app-form" onSubmit={submit}>
            <label>Type<select value={form.type} onChange={(event) => changeType(event.target.value)}><option value="expense">Expense</option><option value="income">Income</option></select></label>
            <label>Amount (₹)<input type="number" min="0.01" step="0.01" required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
            <label>Category<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{categories.map((category) => <option key={category} value={category}>{label(category)}</option>)}</select></label>
            <label>Date<input type="date" max={today} required value={form.transaction_date} onChange={(event) => setForm({ ...form, transaction_date: event.target.value })} /></label>
            <label>Description (optional)<input maxLength="1000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="e.g. Monthly electricity bill" /></label>
            <button className="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save transaction'}</button>
          </form>
          {notice && <p className="inline-notice" role="status">{notice}</p>}
        </section>
        <section className="panel transactions-history">
          <div className="panel-heading"><div><h2>History</h2><p className="muted">Most recent first · up to 200 records</p></div><button type="button" onClick={refresh}>Refresh</button></div>
          {loading && <LoadingState label="Loading transactions…" />}
          {error && <ErrorState error={error} onRetry={refresh} />}
          {!loading && !error && !rows.length && <p className="empty-state">Your history is empty. Add a transaction to get started.</p>}
          {!loading && !error && rows.length > 0 && <ul className="simple-list">{rows.map((row) => <li key={row.id}>
            <div><strong>{row.description || label(row.category)}</strong><small>{row.transaction_date} · {label(row.category)} · Manual entry</small></div>
            <div className="transaction-row-actions"><strong className={row.type === 'income' ? 'income-text' : ''}>{row.type === 'income' ? '+' : '−'}{money.format(Number(row.amount))}</strong><button type="button" className="text-button" aria-label={`Delete ${row.description || row.category}`} onClick={() => remove(row)}>Delete</button></div>
          </li>)}</ul>}
          <p className="fine-print">Transactions are manually recorded and are not synced with a bank account.</p>
        </section>
      </div>
    </section>
  )
}
