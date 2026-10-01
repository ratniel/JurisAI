import { useState } from 'react'
import { ArrowRight, Compass, Heart, Leaf, GraduationCap } from '@phosphor-icons/react'
import { ConstellationField } from '../components/ConstellationField'
import { useNavigate } from 'react-router-dom'

import { createSession } from '../api'

const STARTER_PROMPTS = [
  'I am a farmer in Maharashtra. Which schemes can help with irrigation, crop support, and subsidies?',
  'My family needs help with healthcare costs. Which government schemes should we check first?',
  'I am starting a small business in Karnataka. What schemes support loans, subsidies, or training?',
]

export function HomePage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [launching, setLaunching] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function handleStartSession(initialPrompt = prompt) {
    const message = initialPrompt.trim()
    setLaunching(true)
    setErrorMessage(null)
    try {
      const response = await createSession()
      navigate(`/chat/${response.session.session_id}`, {
        state: message ? { initialPrompt: message, autoSubmit: true } : undefined,
        viewTransition: true,
      })
    } catch (error) {
      setErrorMessage(getSessionLaunchErrorMessage(error))
      setLaunching(false)
    }
  }

  return (
    <main className="landing-shell">
      <header className="site-nav">
        <a className="wordmark" href="/" aria-label="JurisAI home">Juris<span>AI</span></a>
        <button className="nav-start" onClick={() => void handleStartSession('')}>Start chat <ArrowRight size={16} /></button>
      </header>
      <section className="home-hero">
        <ConstellationField />
        <p className="hero-overline"><span className="overline-rule"/> Independent scheme discovery</p>
        <h1>Find support<br/><em>that fits your life.</em></h1>
        <p className="hero-subtitle">A clearer way to discover government schemes and public benefits, grounded in official information.</p>
        <div className="prompt-composer">
          <label className="sr-only" htmlFor="home-prompt">Describe what support you are looking for</label>
          <textarea id="home-prompt" value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleStartSession() } }} placeholder="Tell us a little about your situation…" rows={2}/>
          <div className="prompt-bottom"><span>For example, your state, work, or what you need help with</span><button className="submit-prompt" disabled={launching || !prompt.trim()} onClick={() => void handleStartSession()} aria-label="Find schemes">{launching ? 'Opening…' : <ArrowRight size={20}/>}</button></div>
        </div>
        <div className="category-row" aria-label="Common support areas">
          <button onClick={() => setPrompt('I am a farmer looking for support with crops, irrigation, or equipment.')}><Leaf size={17}/> Agriculture</button>
          <button onClick={() => setPrompt('I am looking for healthcare or insurance support for my family.')}><Heart size={17}/> Healthcare</button>
          <button onClick={() => setPrompt('I am looking for education support or scholarships.')}><GraduationCap size={17}/> Education</button>
          <button onClick={() => setPrompt('I am looking for support to start or grow a small business.')}><Compass size={17}/> Small business</button>
        </div>
        <div className="example-prompts"><span className="example-label">Try asking</span>{STARTER_PROMPTS.map(item => <button key={item} onClick={() => void handleStartSession(item)} disabled={launching}>{item}<ArrowRight size={15}/></button>)}</div>
        {errorMessage ? <p className="inline-error" role="alert">{errorMessage}</p> : null}
      </section>
      <section className="home-lower"><div><span className="section-index">01 / HOW IT WORKS</span><h2>Useful guidance,<br/>without the guesswork.</h2></div><p>Describe your circumstances. JurisAI finds relevant schemes and explains what they offer, who may qualify, and what to do next.</p><span className="independence-note">Independent guidance based on official scheme information.</span></section>
    </main>
  )
}

function getSessionLaunchErrorMessage(error: unknown): string {
  const fallback =
    'JurisAI could not open a chat right now. Please try again in a moment.'

  if (!(error instanceof Error)) {
    return fallback
  }

  const isLocalHost =
    typeof window !== 'undefined' &&
    ['localhost', '127.0.0.1'].includes(window.location.hostname)

  if (
    isLocalHost &&
    (error.message.includes('502') ||
      error.message.includes('Failed to fetch') ||
      error.message.includes('NetworkError'))
  ) {
    return 'The UI is running, but the local chat API is not reachable on 127.0.0.1:8000. Start the backend service, then try again.'
  }

  return error.message || fallback
}
