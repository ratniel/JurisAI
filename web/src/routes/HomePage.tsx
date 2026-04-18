import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createSession } from '../api'

const STARTER_PROMPTS = [
  'I am a farmer in Maharashtra. Which schemes can help with irrigation, crop support, and subsidies?',
  'My family needs help with healthcare costs. Which government schemes should we check first?',
  'I am starting a small business in Karnataka. What schemes support loans, subsidies, or training?',
]

export function HomePage() {
  const navigate = useNavigate()
  const [launching, setLaunching] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function handleStartSession(initialPrompt?: string) {
    setLaunching(true)
    setErrorMessage(null)

    try {
      const response = await createSession()
      navigate(`/chat/${response.session.session_id}`, {
        state: initialPrompt ? { initialPrompt } : undefined,
      })
    } catch (error) {
      setErrorMessage(getSessionLaunchErrorMessage(error))
    } finally {
      setLaunching(false)
    }
  }

  return (
    <main className="landing-shell">
      <section className="landing-frame">
        <header className="landing-header">
          <div>
            <p className="eyebrow">JurisAI</p>
            <h1>Find the right government schemes in one focused conversation.</h1>
          </div>
          <button className="secondary-button" onClick={() => handleStartSession()}>
            Open chat
          </button>
        </header>

        <section className="landing-grid">
          <article className="hero-card">
            <div className="hero-copy-block">
              <p className="section-label">Conversational guidance</p>
              <h2>Clear answers, grounded scheme matches, and a layout built to stay out of the way.</h2>
              <p className="hero-copy">
                Ask in natural language about eligibility, documents, benefits, or
                state-specific schemes. JurisAI keeps the conversation calm and
                surfaces relevant programs beside the answer when they are useful.
              </p>
            </div>

            <div className="hero-actions">
              <button
                className="primary-button"
                onClick={() => handleStartSession()}
                disabled={launching}
              >
                {launching ? 'Opening…' : 'Start a conversation'}
              </button>
              <p className="supporting-note">
                Designed for focused scheme discovery without clutter, filler, or
                workflow noise.
              </p>
            </div>
            {errorMessage ? (
              <section className="inline-error" aria-live="polite">
                {errorMessage}
              </section>
            ) : null}
          </article>

          <aside className="preview-panel">
            <div className="preview-window">
              <div className="preview-toolbar">
                <span className="status-dot" />
                <span>Live scheme guidance</span>
              </div>
              <div className="preview-conversation">
                <div className="preview-bubble preview-user">
                  Which schemes could help a farmer in Vidarbha with irrigation and crop support?
                </div>
                <div className="preview-bubble preview-assistant">
                  I can narrow this by Maharashtra and agriculture support, then
                  surface the strongest scheme matches with next-step guidance.
                </div>
              </div>
              <div className="preview-schemes">
                <div className="preview-scheme">
                  <strong>PM-KISAN</strong>
                  <span>Direct income support for eligible farmer families.</span>
                </div>
                <div className="preview-scheme">
                  <strong>Micro Irrigation Fund</strong>
                  <span>Support for irrigation infrastructure and water-use efficiency.</span>
                </div>
              </div>
            </div>
          </aside>
        </section>

        <section className="starter-section">
          <div className="starter-heading">
            <p className="section-label">Start with a strong prompt</p>
            <h2>Choose a conversation opener</h2>
          </div>
          <div className="starter-grid">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                className="starter-card"
                onClick={() => handleStartSession(prompt)}
                type="button"
                disabled={launching}
              >
                {prompt}
              </button>
            ))}
          </div>
        </section>
      </section>
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
