import { useEffect, useRef, useState } from 'react'
import { getChatCapabilities, getConsentRecords, getConversation, recordConsent, sendChatMessage } from '../api/client'
import { ErrorState } from '../components/ErrorState'
import { OfficialUpdatesPanel } from '../components/OfficialUpdatesPanel'
import './AppPages.css'

function renderAnswer(content) {
  const parts = []
  const sourceLink = /\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g
  let cursor = 0
  let match
  while ((match = sourceLink.exec(content)) !== null) {
    if (match.index > cursor) parts.push(content.slice(cursor, match.index))
    parts.push(<a key={`${match.index}-${match[2]}`} href={match[2]} target="_blank" rel="noreferrer">{match[1]}</a>)
    cursor = sourceLink.lastIndex
  }
  if (cursor < content.length) parts.push(content.slice(cursor))
  return parts
}

function splitGroundedSources(content) {
  const marker = '\n\nSources\n'
  const markerIndex = content.lastIndexOf(marker)
  if (markerIndex < 0) return { answer: content, sources: [] }
  const answer = content.slice(0, markerIndex)
  const sources = content.slice(markerIndex + marker.length).split(/\r?\n/).flatMap((line) => {
    const match = line.match(/^[-*]\s+\[([^\]]+)\]\((https:\/\/[^\s)]+)\)$/)
    return match ? [{ title: match[1], url: match[2] }] : []
  })
  return sources.length ? { answer, sources } : { answer: content, sources: [] }
}

export function Chat() {
  const [messages, setMessages] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [restoring, setRestoring] = useState(() => Boolean(sessionStorage.getItem('finguide-active-conversation')))
  const [capabilities, setCapabilities] = useState(null)
  const [aiConsent, setAiConsent] = useState(false)
  const [consentSaving, setConsentSaving] = useState(false)
  const [error, setError] = useState(null)
  const bottom = useRef(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, sending])

  useEffect(() => {
    const savedId = sessionStorage.getItem('finguide-active-conversation')
    if (!savedId) return
    let cancelled = false
    getConversation(savedId)
      .then((conversation) => {
        if (cancelled) return
        setConversationId(savedId)
        setMessages(conversation.messages)
      })
      .catch(() => sessionStorage.removeItem('finguide-active-conversation'))
      .finally(() => { if (!cancelled) setRestoring(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    getChatCapabilities()
      .then(async (status) => {
        if (cancelled) return
        setCapabilities(status)
        if (status.requires_ai_consent) {
          const records = await getConsentRecords()
          const latest = records.find((item) => item.purpose === 'ai_conversation_processing')
          if (!cancelled) setAiConsent(Boolean(latest?.granted && latest.policy_version === status.consent_policy_version))
        }
      })
      .catch(() => { if (!cancelled) setCapabilities({ provider: 'unavailable', ready: false, requires_ai_consent: false }) })
    return () => { cancelled = true }
  }, [])

  async function changeAiConsent(granted) {
    setConsentSaving(true)
    setError(null)
    try {
      await recordConsent({ purpose: 'ai_conversation_processing', granted, policy_version: capabilities?.consent_policy_version })
      setAiConsent(granted)
    } catch (err) { setError(err) }
    finally { setConsentSaving(false) }
  }

  async function submit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || sending || (capabilities && !capabilities.ready) || (capabilities?.requires_ai_consent && !aiConsent)) return
    setDraft('')
    setError(null)
    setSending(true)
    try {
      const result = await sendChatMessage({ message: text, conversation_id: conversationId })
      setConversationId(result.conversation_id)
      sessionStorage.setItem('finguide-active-conversation', result.conversation_id)
      setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', content: text }, result.reply])
    } catch (err) {
      setDraft(text)
      setError(err)
    } finally { setSending(false) }
  }

  return (
    <section className="app-page chat-page">
      <div className="page-heading"><div><p className="eyebrow">ASK A QUESTION</p><h1>FinGuide+ Chat</h1><p className="muted">{capabilities?.provider === 'Gemini' ? 'Gemini financial learning with source-linked web grounding for current market questions.' : capabilities?.provider === 'OpenAI' ? 'An AI assistant powered by OpenAI for general financial learning.' : 'A rule-based assistant for general financial questions.'}</p></div><button type="button" onClick={() => { sessionStorage.removeItem('finguide-active-conversation'); setMessages([]); setConversationId(null); setError(null) }}>New chat</button></div>
      <div className="chat-layout-grid">
      <div className="chat-panel">
        {['OpenAI', 'Gemini'].includes(capabilities?.provider) && capabilities.ready && <div className="ai-consent-panel"><label><input type="checkbox" checked={aiConsent} disabled={consentSaving} onChange={(event) => changeAiConsent(event.target.checked)} /> Allow FinGuide+ to send my chat messages and recent conversation context to {capabilities.provider} to generate replies.</label><small>Your saved profile is not sent. {capabilities.provider === 'Gemini' && <>For current-market questions, FinGuide also sends the latest question and selected public NIFTY 50 data or RBI/SEBI headline snippets when relevant. Earlier chat turns and your saved profile are excluded. Google may store the query, public market context, and output for up to 30 days. Search grounding may have usage charges depending on your Gemini project and quota. For Gemini's unpaid API quota, Google may use prompts and responses to improve products and human reviewers may process them. </>}Avoid sensitive financial or identity information. Review <a href={capabilities.provider === 'Gemini' ? 'https://ai.google.dev/gemini-api/terms' : 'https://developers.openai.com/api/docs/guides/your-data'} target="_blank" rel="noreferrer">{capabilities.provider} API data terms</a>. You can revoke permission here at any time.</small></div>}
        {['OpenAI', 'Gemini'].includes(capabilities?.provider) && !capabilities.ready && <div className="callout"><strong>AI provider setup is incomplete</strong><p>{capabilities.provider === 'Gemini' ? 'Set GEMINI_API_KEY and GEMINI_MODEL in the backend .env file, then recreate the backend container. The API key stays on the server.' : 'Configure OPENAI_API_KEY and OPENAI_MODEL in the backend environment, then restart the backend. The API key stays on the server.'}</p></div>}
        {restoring && <p className="muted" role="status">Restoring your recent conversation…</p>}
        {!messages.length && !restoring && <div className="chat-welcome"><h2>What would you like help thinking through?</h2><p>Try asking about budgeting, emergency savings, or the information you should gather before making a financial decision.</p><p className="fine-print">Replies are general guidance, not personalized professional advice. The assistant will not make transactions or act on your accounts.</p></div>}
        {messages.map((message) => { const grounded = message.role === 'assistant' ? splitGroundedSources(message.content) : { answer: message.content, sources: [] }; return <article key={message.id} className={`chat-message ${message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}`}><span>{message.role === 'user' ? 'You' : 'FinGuide+'}</span><p>{renderAnswer(grounded.answer)}</p>{grounded.sources.length > 0 && <div className="chat-grounded-sources"><strong>Sources</strong><ul>{grounded.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></li>)}</ul><small>Web information can be delayed or change. Check the provider for the latest official figure.</small></div>}{message.search_suggestions_html && <iframe className="chat-search-suggestions" title="Google Search suggestions" sandbox="allow-popups" srcDoc={message.search_suggestions_html} />}</article> })}
        {sending && <p className="muted" role="status">FinGuide+ is thinking…</p>}
        {error && <ErrorState error={error} />}
        <div ref={bottom} />
        <form className="chat-composer" onSubmit={submit}><label className="sr-only" htmlFor="chat-draft">Your message</label><textarea id="chat-draft" rows="3" maxLength="4000" placeholder="Write a question…" value={draft} onChange={(event) => setDraft(event.target.value)} /><button className="primary" type="submit" disabled={sending || !draft.trim() || (capabilities && !capabilities.ready) || (capabilities?.requires_ai_consent && !aiConsent)}>{sending ? 'Sending…' : 'Send'}</button></form>
        <p className="fine-print">Messages are saved to your account. This browser tab restores its most recent conversation; start a new chat to begin another one.</p>
      </div>
      <aside className="chat-page-rail">
        <OfficialUpdatesPanel compact />
        <section className="panel chat-questions-panel">
          <p className="eyebrow">GET STARTED</p>
          <h2>Questions you can ask</h2>
          <div className="chat-question-list">
            <button type="button" onClick={() => setDraft('Explain the RBI repo rate in simple terms.')}>Explain a financial term</button>
            <button type="button" onClick={() => setDraft('What should I check before comparing two mutual funds?')}>Compare two funds</button>
            <button type="button" onClick={() => setDraft('Summarize the latest official RBI and SEBI updates shown here.')}>Summarize official updates</button>
          </div>
          <p className="fine-print">Questions only fill the chat box. They are sent when you choose Send.</p>
        </section>
      </aside>
      </div>
    </section>
  )
}
