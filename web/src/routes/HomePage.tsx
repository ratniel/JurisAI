import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createSession } from '../api'
import { ThemeToggleButton } from '../components/ThemeToggleButton'
import { BrandCrest, InstitutionIllustration, UiIcon } from '../components/UiArt'

const STARTER_PROMPTS = [
  'I am a woman entrepreneur in Maharashtra. Which schemes can help me start and grow?',
  'Find scholarships I may be eligible for as a student from a low-income family.',
  'Show schemes for medical support, insurance, and healthcare costs.',
  'What schemes can help rural families with livelihoods, housing, and support?',
]

const GOALS = [
  {
    title: 'Clarity',
    description: 'Clear hierarchy and information scent to reduce cognitive load.',
    icon: 'target' as const,
  },
  {
    title: 'Trust',
    description: 'Show sources, status, and scheme context to build confidence.',
    icon: 'shield' as const,
  },
  {
    title: 'Speed',
    description: 'Faster answers with smoother streaming and smart suggestions.',
    icon: 'bolt' as const,
  },
  {
    title: 'Responsiveness',
    description: 'A cohesive experience across desktop, tablet, and mobile.',
    icon: 'layers' as const,
  },
]

const PRINCIPLES = [
  {
    title: 'Chat-first hierarchy',
    body: 'Make the conversation the hero. Keep chrome quiet and purposeful.',
    icon: 'chat' as const,
  },
  {
    title: 'Transparent retrieval',
    body: 'Show what we searched, where it came from, and why it fits.',
    icon: 'search' as const,
  },
  {
    title: 'Progressive disclosure',
    body: 'Reveal the right level of detail at the right time without overload.',
    icon: 'layers' as const,
  },
  {
    title: 'Fast, calm interactions',
    body: 'Use subtle motion and grounded feedback instead of noisy system states.',
    icon: 'spark' as const,
  },
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
    <main className="case-study-page">
      <section className="case-study-shell">
        <div className="project-ribbon">
          <span className="project-ribbon-dot" />
          <span>JurisAI Project</span>
          <span className="project-ribbon-separator">01 / Overview</span>
        </div>

        <section className="hero-overview">
          <div className="hero-overview-copy">
            <div className="hero-heading-stack">
              <div className="brand-lockup">
                <BrandCrest className="brand-crest" />
                <div>
                  <p className="brand-name">JurisAI</p>
                  <p className="brand-tagline">Legal clarity for everyone.</p>
                </div>
              </div>

              <h1 className="display-hero">
                Juris<span>AI</span>
              </h1>
              <p className="hero-subtitle">
                Redesigning the main chat experience for a modern, trustworthy
                government-schemes assistant.
              </p>
            </div>

            <div className="overview-grid">
              <article className="overview-card">
                <p className="section-kicker">Project overview</p>
                <p>
                  JurisAI helps citizens discover the right government schemes through
                  conversational search. The next version focuses on clarity, visible
                  retrieval, stronger trust signals, and a calmer, more premium product
                  surface.
                </p>
              </article>

              <div className="goal-grid">
                {GOALS.map((goal) => (
                  <article key={goal.title} className="goal-card">
                    <UiIcon className="goal-icon" name={goal.icon} />
                    <h2>{goal.title}</h2>
                    <p>{goal.description}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>

          <InstitutionIllustration className="hero-illustration" />
        </section>

        <section className="preview-stage">
          <div className="preview-stage-header">
            <div>
              <p className="section-kicker">Redesigned main chat experience</p>
              <h2>The conversation becomes the center, with shortlist context beside it.</h2>
            </div>
            <button
              className="primary-button"
              disabled={launching}
              onClick={() => handleStartSession()}
              type="button"
            >
              {launching ? 'Opening…' : 'Open the live chat'}
            </button>
          </div>

          <article className="showcase-frame">
            <aside className="showcase-sidebar">
              <div className="sidebar-brand">
                <BrandCrest className="sidebar-brand-crest" />
                <span>JurisAI</span>
              </div>
              <nav className="sidebar-nav" aria-label="Primary">
                {[
                  ['Chat', 'chat'],
                  ['Schemes', 'schemes'],
                  ['Saved', 'save'],
                  ['History', 'history'],
                  ['Notifications', 'bell'],
                  ['Settings', 'settings'],
                ].map(([label, icon], index) => (
                  <div
                    key={label}
                    className={`sidebar-nav-item ${index === 0 ? 'is-active' : ''}`}
                  >
                    <UiIcon className="sidebar-nav-icon" name={icon as Parameters<typeof UiIcon>[0]['name']} />
                    <span>{label}</span>
                    {label === 'Notifications' ? <span className="count-pill">3</span> : null}
                  </div>
                ))}
              </nav>

              <div className="sidebar-mode-card">
                <p className="sidebar-mode-label">Citizen mode</p>
                <strong>General guidance</strong>
                <p>
                  Discover schemes that match your situation, not just the popular
                  ones.
                </p>
              </div>
            </aside>

            <div className="showcase-main">
              <header className="app-topbar">
                <div className="topbar-left">
                  <UiIcon className="topbar-menu" name="menu" />
                  <div className="surface-brand">
                    <BrandCrest className="surface-brand-crest" />
                    <span>JurisAI</span>
                    <span className="beta-chip">Beta</span>
                  </div>
                  <span className="status-pill">
                    <span className="status-dot" />
                    Conversation
                  </span>
                </div>

                <div className="topbar-actions">
                  <button className="quiet-button" type="button">
                    <UiIcon name="help" />
                    Help
                  </button>
                  <ThemeToggleButton />
                  <button className="primary-pill-button topbar-primary-button" type="button">
                    <UiIcon name="plus" />
                    New
                  </button>
                  <div className="avatar-pill">
                    <span>R</span>
                    <span>Ratniel</span>
                  </div>
                </div>
              </header>

              <div className="showcase-columns">
                <section className="showcase-conversation">
                  <div className="message-row is-user">
                    <div className="message-bubble-preview user-preview">
                      Which government schemes are available for a woman entrepreneur
                      in Maharashtra?
                    </div>
                  </div>

                  <div className="message-row">
                    <div className="message-bubble-preview assistant-preview">
                      <div className="assistant-preview-header">
                        <div className="assistant-name">
                          <BrandCrest className="mini-crest" />
                          <span>JurisAI</span>
                        </div>
                        <span>10:32 AM</span>
                      </div>
                      <p>
                        Here are relevant government schemes for women entrepreneurs
                        in Maharashtra. These schemes offer funding support, training,
                        mentorship, and market access.
                      </p>
                      <div className="preview-scheme-stack">
                        <div className="preview-scheme-card">
                          <div>
                            <strong>Mukhyamantri Mahila Udyam Nidhi</strong>
                            <p>
                              Collateral-free loans up to Rs 10 lakh for women
                              entrepreneurs in manufacturing and services.
                            </p>
                          </div>
                          <span className="match-badge high">High Match</span>
                        </div>
                        <div className="preview-scheme-card">
                          <div>
                            <strong>MUDRA Yojana</strong>
                            <p>
                              Loans for non-corporate small businesses including
                              women-led enterprises.
                            </p>
                          </div>
                          <span className="match-badge high">High Match</span>
                        </div>
                        <div className="preview-chip-row">
                          <span className="source-chip">Retrieved from 23 sources</span>
                          <span className="source-chip">View sources</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="preview-suggestion-row">
                    <span className="suggestion-chip">Eligibility for MMUMN</span>
                    <span className="suggestion-chip">How to apply for MUDRA</span>
                    <span className="suggestion-chip">Schemes for rural women</span>
                  </div>

                  <div className="preview-composer">
                    <p>Ask about schemes, eligibility, benefits...</p>
                    <div className="preview-composer-actions">
                      <span className="composer-chip">
                        <UiIcon name="attach" />
                        Attach
                      </span>
                      <div className="composer-action-cluster">
                        <button className="quiet-icon-button composer-voice-button" type="button">
                          <UiIcon name="microphone" />
                        </button>
                        <button className="send-fab" type="button">
                          <UiIcon name="send" />
                        </button>
                      </div>
                    </div>
                  </div>
                </section>

                <aside className="showcase-shortlist">
                  <div className="shortlist-panel-header">
                    <div>
                      <h3>Scheme shortlist</h3>
                      <p>Shortlist is personalized to your query and available context.</p>
                    </div>
                    <span className="count-pill">5</span>
                  </div>

                  {[
                    ['MMUMN', 'Loans up to Rs 10 lakh for women entrepreneurs.', 'High Match'],
                    ['MUDRA Yojana', 'Collateral-free loans for small businesses.', 'High Match'],
                    ['MSInS Women Startup Program', 'Seed support for women-led startups.', 'Medium Match'],
                    ['Stand Up India', 'Loans between Rs 10 lakh and Rs 1 crore.', 'Medium Match'],
                    ['MAVIM', 'Livelihood assistance for women in Maharashtra.', 'Low Match'],
                  ].map(([title, summary, match], index) => (
                    <article key={title} className="shortlist-card-preview">
                      <div className="shortlist-rank">{index + 1}</div>
                      <div className="shortlist-card-body">
                        <div className="shortlist-card-copy">
                          <h4>{title}</h4>
                        </div>
                        <p>{summary}</p>
                        <div className="tag-row">
                          <span className="tag">Loan</span>
                          <span className="tag">Maharashtra</span>
                          <span className="tag">Women</span>
                        </div>
                      </div>
                      <span
                        className={`match-badge ${
                          match === 'High Match'
                            ? 'high'
                            : match === 'Medium Match'
                              ? 'medium'
                              : 'low'
                        }`}
                      >
                        {match}
                      </span>
                    </article>
                  ))}

                  <button className="wide-ghost-button" type="button">
                    View all matching schemes
                    <UiIcon name="external" />
                  </button>
                </aside>
              </div>
            </div>
          </article>
        </section>

        <section className="principles-strip">
          {PRINCIPLES.map((principle) => (
            <article key={principle.title} className="principle-card">
              <UiIcon className="principle-icon" name={principle.icon} />
              <div>
                <h3>{principle.title}</h3>
                <p>{principle.body}</p>
              </div>
            </article>
          ))}
        </section>

        <section className="launcher-section">
          <div className="launcher-copy">
            <p className="section-kicker">Start with a strong prompt</p>
            <h2>Launch the live UI with one of the exact discovery scenarios.</h2>
          </div>

          <div className="launcher-grid">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                className="launcher-card"
                disabled={launching}
                onClick={() => handleStartSession(prompt)}
                type="button"
              >
                <span>{prompt}</span>
                <UiIcon name="external" />
              </button>
            ))}
          </div>

          {errorMessage ? (
            <section className="inline-notice error" aria-live="polite">
              {errorMessage}
            </section>
          ) : null}
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
