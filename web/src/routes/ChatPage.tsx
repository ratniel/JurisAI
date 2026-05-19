import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { createMessage, getSession } from '../api'
import { ThemeToggleButton } from '../components/ThemeToggleButton'
import { BrandCrest, UiIcon } from '../components/UiArt'
import {
  buildSchemeSummary,
  buildSchemeTags,
  getDisplaySourceLinks,
  getPrimarySchemeUrl,
  humanizeToken,
} from './chatPageUtils'
import type {
  ChatMessageRecord,
  ChatSessionRecord,
  StreamEventMap,
  TopSchemesArtifact,
  TopSchemeArtifactEntry,
} from '../types'

type StageEntry = {
  stage: string
  detail: string
}

type ChatLocationState = {
  initialPrompt?: string
}

type ShortlistScheme = TopSchemeArtifactEntry & {
  matchLabel: 'High Match' | 'Medium Match' | 'Low Match'
  summary: string
  tags: string[]
}

const COLLAPSE_PREVIEW_LENGTH = 360

const FRIENDLY_STAGE_LABELS: Record<string, string> = {
  run_started: 'Thinking',
  intent_classified: 'Understanding your request',
  decision_made: 'Planning the next step',
  retrieval_planned: 'Preparing search tools',
  retrieval_started: 'Searching schemes',
  retrieval_completed: 'Reviewing retrieved schemes',
  artifact_ready: 'Shortlist ready',
  response_generated: 'Drafting answer',
}

const STARTER_PROMPTS = [
  'Which government schemes are available for a woman entrepreneur in Maharashtra?',
  'Which scholarships may I be eligible for as a student from a low-income family?',
  'Which government schemes can help with medical support and healthcare costs?',
  'What government schemes can help rural families with livelihoods and support?',
]

const LANDING_FEATURES = [
  {
    title: 'Tell us your situation',
    description: 'Share what you need, your location, and your profile.',
    icon: 'chat' as const,
  },
  {
    title: 'We uncover matches',
    description: 'We search across thousands of government schemes.',
    icon: 'search' as const,
  },
  {
    title: 'Clear, guided answers',
    description: 'Understand eligibility, benefits, and how to apply.',
    icon: 'shield' as const,
  },
]

const DEMO_SHORTLIST: ShortlistScheme[] = [
  {
    scheme_id: 'mmumn',
    name: 'Mukhyamantri Mahila Udyam Nidhi',
    state: 'Maharashtra',
    level: 'state',
    provider: 'Maharashtra',
    details:
      'Collateral-free loans up to Rs 10 lakh for women entrepreneurs in manufacturing and service sectors.',
    benefits:
      '- Loan assistance up to Rs 10 lakh\n- Concessional support for women-led units\n- Useful for starting or expanding eligible businesses',
    eligibility:
      '- Woman applicant in Maharashtra\n- Viable business plan\n- Applicant aligned to eligible sector criteria',
    documents_required:
      '- Aadhaar card\n- PAN card\n- Address proof\n- Business proposal or registration details',
    references: [
      { text: 'mahaswayam.gov.in', url: 'https://mahaswayam.gov.in' },
      { text: 'maharashtra.gov.in', url: 'https://maharashtra.gov.in' },
    ],
    retrieval_reason:
      'Strong state-level fit for women entrepreneurs seeking financing in Maharashtra.',
    matchLabel: 'High Match',
    summary:
      'Collateral-free loans up to Rs 10 lakh for women entrepreneurs in manufacturing and services.',
    tags: ['Loan', 'Maharashtra', 'Women'],
  },
  {
    scheme_id: 'mudra',
    name: 'MUDRA Yojana',
    level: 'central',
    provider: 'Government of India',
    details:
      'Loans for non-corporate small businesses, including women-led enterprises at the micro and small business stage.',
    benefits:
      '- Shishu, Kishor, and Tarun loan categories\n- Works for early and growth-stage businesses\n- Widely available through lending partners',
    eligibility:
      '- Non-corporate small business applicant\n- Viable business purpose\n- Meets lender documentation norms',
    references: [{ text: 'mudra.org.in', url: 'https://www.mudra.org.in' }],
    retrieval_reason:
      'Relevant central scheme for entrepreneurship and accessible alongside state support.',
    matchLabel: 'High Match',
    summary:
      'Collateral-free loans for non-corporate small businesses including women-led enterprises.',
    tags: ['Loan', 'Central', 'Women'],
  },
  {
    scheme_id: 'msins',
    name: 'MSInS Women Startup Program',
    state: 'Maharashtra',
    level: 'state',
    provider: 'Maharashtra',
    details:
      'Incubation and seed support for women-led startups through the Maharashtra innovation ecosystem.',
    benefits:
      '- Mentorship support\n- Startup incubation access\n- Potential seed-funding pathways',
    eligibility:
      '- Startup or early-stage founder\n- Women-led team or founder criteria\n- Maharashtra-linked business presence',
    retrieval_reason:
      'Useful when the user is exploring startup support in addition to loans.',
    matchLabel: 'Medium Match',
    summary:
      'Incubation and seed support for women-led startups and innovation-focused businesses.',
    tags: ['Startup', 'Maharashtra', 'Grant'],
  },
  {
    scheme_id: 'stand-up-india',
    name: 'Stand Up India',
    level: 'central',
    provider: 'Government of India',
    details:
      'Loans between Rs 10 lakh and Rs 1 crore for greenfield enterprises run by women and eligible communities.',
    benefits:
      '- Greenfield enterprise support\n- Large-ticket loan range\n- Structured bank-led access',
    eligibility:
      '- New enterprise setup\n- Eligible woman entrepreneur\n- Meets participating bank requirements',
    retrieval_reason:
      'Strong follow-up option for women entrepreneurs planning a new enterprise with larger capital needs.',
    matchLabel: 'Medium Match',
    summary:
      'Loans between Rs 10 lakh and Rs 1 crore for women entrepreneurs setting up greenfield enterprises.',
    tags: ['Loan', 'Central', 'Women'],
  },
  {
    scheme_id: 'mavim',
    name: 'Mahila Arthik Vikas Mahamandal',
    state: 'Maharashtra',
    level: 'state',
    provider: 'Maharashtra',
    details:
      'Livelihood and financial assistance support through women-focused self-help and development pathways in Maharashtra.',
    benefits:
      '- Women-focused livelihood support\n- Self-help group enablement\n- Skill and enterprise linkage',
    eligibility:
      '- Maharashtra-based eligible women beneficiaries\n- Program-specific criteria vary by support line',
    retrieval_reason:
      'Relevant for livelihood and development support, though less direct than loan-specific options.',
    matchLabel: 'Low Match',
    summary:
      'Financial assistance for women’s economic development initiatives and livelihood support.',
    tags: ['Support', 'Maharashtra', 'Women'],
  },
]

const DEFAULT_WORKFLOW_STEPS = [
  { label: 'Understanding user intent', status: 'complete' },
  { label: 'Extracting location and profile context', status: 'complete' },
  { label: 'Retrieving relevant schemes', status: 'active' },
  { label: 'Ranking possible matches', status: 'pending' },
  { label: 'Checking eligibility signals', status: 'pending' },
  { label: 'Grounding with official sources', status: 'pending' },
  { label: 'Drafting the answer', status: 'pending' },
]

export function ChatPage() {
  const { sessionId = '' } = useParams()
  const location = useLocation()
  const [session, setSession] = useState<ChatSessionRecord | null>(null)
  const [composer, setComposer] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [draftAnswer, setDraftAnswer] = useState('')
  const [stageLog, setStageLog] = useState<StageEntry[]>([])
  const [stageHistoryExpanded, setStageHistoryExpanded] = useState(false)
  const [currentArtifact, setCurrentArtifact] = useState<TopSchemesArtifact | null>(
    null,
  )
  const [sessionErrorMessage, setSessionErrorMessage] = useState<string | null>(null)
  const [runErrorMessage, setRunErrorMessage] = useState<string | null>(null)
  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null)
  const [showShortlistDrawer, setShowShortlistDrawer] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const initialPromptAppliedRef = useRef(false)
  const composerFormRef = useRef<HTMLFormElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const messageScrollAreaRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadSession() {
      setLoading(true)
      try {
        const response = await getSession(sessionId)
        if (cancelled) {
          return
        }

        const latestArtifact =
          response.session.session_snapshot.latest_top_schemes_artifact ??
          response.session.artifacts.at(-1) ??
          null

        setSession(response.session)
        setCurrentArtifact(latestArtifact)
        setSessionErrorMessage(null)
      } catch (error) {
        if (!cancelled) {
          setSessionErrorMessage(
            error instanceof Error ? error.message : 'Failed to load session.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadSession()

    return () => {
      cancelled = true
      eventSourceRef.current?.close()
    }
  }, [sessionId])

  useEffect(() => {
    if (initialPromptAppliedRef.current) {
      return
    }

    const state = location.state as ChatLocationState | null
    const initialPrompt = state?.initialPrompt?.trim()
    if (!initialPrompt) {
      return
    }

    setComposer(initialPrompt)
    initialPromptAppliedRef.current = true
  }, [location.state])

  useEffect(() => {
    const composerElement = composerRef.current
    if (!composerElement) {
      return
    }

    composerElement.style.height = 'auto'
    composerElement.style.height = `${Math.min(composerElement.scrollHeight, 220)}px`
  }, [composer])

  const transcript = useMemo(() => session?.messages ?? [], [session?.messages])

  useEffect(() => {
    const scrollArea = messageScrollAreaRef.current
    if (!scrollArea) {
      return
    }

    scrollArea.scrollTo({
      top: scrollArea.scrollHeight,
      behavior: sending ? 'smooth' : 'auto',
    })
  }, [draftAnswer, sending, stageLog.length, transcript.length])

  const latestStage = stageLog.at(-1)
  const latestStageDescription = latestStage ? describeStageEntry(latestStage) : null
  const statusLabel = runErrorMessage
    ? 'Needs attention'
    : sending
      ? FRIENDLY_STAGE_LABELS[latestStage?.stage ?? 'run_started'] ?? 'Working'
      : 'Ready'
  const showLiveAssistant =
    sending ||
    Boolean(draftAnswer.trim()) ||
    Boolean(runErrorMessage) ||
    stageLog.length > 0
  const hasConversation = transcript.length > 0 || showLiveAssistant
  const shortlist = useMemo(
    () =>
      mapShortlist(currentArtifact?.schemes, {
        includeDemoFallback: !loading && !hasConversation,
      }),
    [currentArtifact?.schemes, hasConversation, loading],
  )

  useEffect(() => {
    if (!shortlist.length) {
      setSelectedSchemeId(null)
      return
    }

    setSelectedSchemeId((current) =>
      current && shortlist.some((scheme) => scheme.scheme_id === current)
        ? current
        : shortlist[0].scheme_id,
    )
  }, [shortlist])

  const selectedScheme =
    shortlist.find((scheme) => scheme.scheme_id === selectedSchemeId) ?? shortlist[0] ?? null
  const conversationTitle = getConversationTitle(transcript)
  const sourceCount = getDisplaySourceLinks(selectedScheme).length
  const followUpChips = buildFollowUpChips(selectedScheme)
  const workflowSteps = buildWorkflowSteps(stageLog)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = composer.trim()
    if (!message || !session) {
      return
    }

    setRunErrorMessage(null)
    setSending(true)
    setDraftAnswer('')
    setStageLog([])
    setStageHistoryExpanded(false)
    setComposer('')
    setSession((current) =>
      current
        ? {
            ...current,
            messages: [
              ...current.messages,
              {
                message_id: `optimistic-${Date.now()}`,
                role: 'user',
                content: message,
                created_at: new Date().toISOString(),
              },
            ],
          }
        : current,
    )

    try {
      const response = await createMessage(session.session_id, message)
      let terminalEventReceived = false
      eventSourceRef.current?.close()
      const source = new EventSource(response.stream_path)
      eventSourceRef.current = source

      source.addEventListener('run_started', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['run_started']
        setRunErrorMessage(null)
        setStageLog([{ stage: 'run_started', detail: payload.message }])
      })

      source.addEventListener('stage_update', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['stage_update']
        setStageLog((current) => [...current, payload])
      })

      source.addEventListener('answer_delta', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['answer_delta']
        setDraftAnswer((current) => current + payload.delta)
      })

      source.addEventListener('artifact_ready', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['artifact_ready']
        setCurrentArtifact(payload.artifact)
        setStageLog((current) => [
          ...current,
          {
            stage: 'artifact_ready',
            detail: `${payload.artifact.schemes.length} scheme(s) ready to review`,
          },
        ])
      })

      source.addEventListener('run_completed', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['run_completed']
        terminalEventReceived = true
        setDraftAnswer('')
        setStageLog([])
        setStageHistoryExpanded(false)
        setRunErrorMessage(null)
        setSession(payload.session)
        setCurrentArtifact(
          payload.session.session_snapshot.latest_top_schemes_artifact ??
            payload.session.artifacts.at(-1) ??
            null,
        )
        setSending(false)
        source.close()
        eventSourceRef.current = null
      })

      source.addEventListener('run_failed', (sse) => {
        const payload = JSON.parse(
          (sse as MessageEvent<string>).data,
        ) as StreamEventMap['run_failed']
        terminalEventReceived = true
        setRunErrorMessage(payload.error)
        setSending(false)
        source.close()
        eventSourceRef.current = null
      })

      source.onerror = () => {
        if (terminalEventReceived) {
          return
        }

        setRunErrorMessage(
          'The live response stream disconnected before the run finished. Any text already shown has been kept below.',
        )
        setSending(false)
        source.close()
        eventSourceRef.current = null
      }
    } catch (error) {
      setSending(false)
      setRunErrorMessage(
        error instanceof Error ? error.message : 'Failed to send message.',
      )
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return
    }

    event.preventDefault()
    if (!composer.trim() || sending) {
      return
    }

    composerFormRef.current?.requestSubmit()
  }

  return (
    <main className="chat-page">
      <section className="chat-product-shell">
        <aside className="product-sidebar">
          <div className="sidebar-brand">
            <BrandCrest className="sidebar-brand-crest" />
            <div>
              <span>JurisAI</span>
              <small>Discovery assistant</small>
            </div>
          </div>

          <nav className="sidebar-nav" aria-label="Primary">
            <SidebarNavItem active icon="chat" label="Chat" />
            <SidebarNavItem icon="schemes" label="Schemes" />
            <SidebarNavItem icon="save" label="Saved" />
            <SidebarNavItem icon="history" label="History" />
            <SidebarNavItem badge="3" icon="bell" label="Notifications" />
            <SidebarNavItem icon="settings" label="Settings" />
          </nav>

          <div className="sidebar-mode-card">
            <p className="sidebar-mode-label">Citizen mode</p>
            <strong>General guidance</strong>
            <p>
              We help you discover schemes that match your situation, not just the
              popular ones.
            </p>
            <Link className="mode-link" to="/">
              Learn more
              <UiIcon name="external" />
            </Link>
          </div>
        </aside>

        <div className="product-main">
          <header className="app-topbar">
            <div className="topbar-left">
              <button
                className="quiet-icon-button mobile-only"
                onClick={() => setShowShortlistDrawer((current) => !current)}
                type="button"
              >
                <UiIcon name="layers" />
              </button>

              <div className="surface-brand">
                <BrandCrest className="surface-brand-crest" />
                <span>JurisAI</span>
                <span className="beta-chip">Beta</span>
              </div>

              <span className={`status-pill ${sending ? 'is-live' : ''}`}>
                <span className="status-dot" />
                {sending ? 'Live' : 'Conversation'}
              </span>

              <div className="conversation-chip">{conversationTitle}</div>
            </div>

            <div className="topbar-actions">
              <button className="quiet-button" type="button">
                <UiIcon name="help" />
                Help
              </button>

              <ThemeToggleButton />

              {sourceCount ? (
                <button className="quiet-button" type="button">
                  <UiIcon name="document" />
                  Sources
                </button>
              ) : null}

              <Link className="primary-pill-button topbar-primary-button" to="/">
                <UiIcon name="plus" />
                New
              </Link>

              <div className="avatar-pill">
                <span>R</span>
                <span>Ratniel</span>
              </div>
            </div>
          </header>

          <div className="product-content">
            <section className="conversation-surface">
              {loading ? (
                <section className="inline-notice">Loading conversation…</section>
              ) : sessionErrorMessage ? (
                <section className="inline-notice error">{sessionErrorMessage}</section>
              ) : (
                <>
                  {!hasConversation ? (
                    <section className="landing-conversation">
                      <div className="landing-copy">
                        <h1>Welcome to JurisAI</h1>
                        <p>
                          Discover schemes that match your needs, not just the popular
                          ones.
                        </p>
                      </div>

                      <div className="landing-feature-grid">
                        {LANDING_FEATURES.map((feature) => (
                          <article key={feature.title} className="landing-feature-card">
                            <UiIcon className="landing-feature-icon" name={feature.icon} />
                            <h2>{feature.title}</h2>
                            <p>{feature.description}</p>
                          </article>
                        ))}
                      </div>

                      <ComposerCard
                        composer={composer}
                        composerFormRef={composerFormRef}
                        composerRef={composerRef}
                        disabled={sending}
                        helperText={
                          latestStageDescription?.detail ??
                          'Shift + Enter for a new line'
                        }
                        onChange={setComposer}
                        onKeyDown={handleComposerKeyDown}
                        onSubmit={handleSubmit}
                        submitLabel={sending ? 'Working…' : 'Send'}
                      />

                      <div className="starter-card-grid">
                        {STARTER_PROMPTS.map((prompt) => (
                          <button
                            key={prompt}
                            className="starter-prompt-card"
                            onClick={() => setComposer(prompt)}
                            type="button"
                          >
                            <span>{prompt}</span>
                            <UiIcon name="external" />
                          </button>
                        ))}
                      </div>

                      <button className="explore-all-card" type="button">
                        <div>
                          <strong>Explore all schemes</strong>
                          <p>Browse by category, ministry, and your state.</p>
                        </div>
                        <UiIcon name="external" />
                      </button>

                      <div className="landing-meta-grid">
                        <section className="workflow-card">
                          <div className="workflow-card-header">
                            <div>
                              <h3>How JurisAI is helping</h3>
                              <p>Human-readable progress without technical noise.</p>
                            </div>
                            <button className="inline-link-button" type="button">
                              Hide steps
                            </button>
                          </div>

                          <div className="workflow-step-list">
                            {workflowSteps.map((step, index) => (
                              <div
                                key={step.label}
                                className={`workflow-step workflow-step-${step.status}`}
                              >
                                <span className="workflow-step-index">{index + 1}</span>
                                <div>
                                  <strong>{step.label}</strong>
                                  <span>
                                    {step.status === 'complete'
                                      ? 'Complete'
                                      : step.status === 'active'
                                        ? 'In progress'
                                        : 'Pending'}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </section>

                        <section className="workflow-visual-card">
                          <div className="workflow-card-header">
                            <div>
                              <h3>A peek behind the scenes</h3>
                              <p>Understand how JurisAI moves from your query to a grounded answer.</p>
                            </div>
                          </div>

                          <div className="workflow-visual-track">
                            {[
                              'Idle',
                              'Understanding',
                              'Retrieving',
                              'Shortlist ready',
                              'Answer streaming',
                            ].map((label, index) => (
                              <div
                                key={label}
                                className={`workflow-visual-node ${
                                  index < 2 ? 'is-complete' : index === 2 ? 'is-active' : ''
                                }`}
                              >
                                <div className="workflow-visual-icon">
                                  <UiIcon
                                    name={
                                      index === 0
                                        ? 'chat'
                                        : index === 1
                                          ? 'user'
                                          : index === 2
                                            ? 'search'
                                            : index === 3
                                              ? 'layers'
                                              : 'spark'
                                    }
                                  />
                                </div>
                                <strong>{label}</strong>
                              </div>
                            ))}
                          </div>

                          <div className="inline-notice">
                            <UiIcon name="shield" />
                            You stay in control. Interrupt, refine, or ask follow-up
                            questions at any time.
                          </div>
                        </section>
                      </div>
                    </section>
                  ) : (
                    <section className="conversation-thread">
                      <div className="conversation-heading">
                        <div>
                          <p className="section-kicker">Conversation</p>
                          <h1>Ask follow-ups naturally</h1>
                        </div>
                        <span className="status-ghost-pill">{statusLabel}</span>
                      </div>

                      <div className="thread-scroll" ref={messageScrollAreaRef}>
                        {transcript.map((message) => (
                          <ChatMessageBubble key={message.message_id} message={message} />
                        ))}

                        {showLiveAssistant ? (
                          <LiveAssistantBubble
                            draftAnswer={draftAnswer}
                            errorMessage={runErrorMessage}
                            expanded={stageHistoryExpanded}
                            onToggleExpanded={() =>
                              setStageHistoryExpanded((current) => !current)
                            }
                            stageLog={stageLog}
                          />
                        ) : null}
                      </div>

                      <div className="follow-up-row">
                        {followUpChips.map((chip) => (
                          <button key={chip} className="suggestion-chip" type="button">
                            {chip}
                          </button>
                        ))}
                      </div>

                      {shortlist.length ? (
                        <button
                          className="mobile-shortlist-button mobile-only"
                          onClick={() => setShowShortlistDrawer((current) => !current)}
                          type="button"
                        >
                          {showShortlistDrawer ? 'Hide' : 'Show'} scheme shortlist ({shortlist.length})
                        </button>
                      ) : null}

                      <ComposerCard
                        composer={composer}
                        composerFormRef={composerFormRef}
                        composerRef={composerRef}
                        disabled={sending}
                        helperText={
                          latestStageDescription?.detail ??
                          'Shift + Enter for a new line'
                        }
                        onChange={setComposer}
                        onKeyDown={handleComposerKeyDown}
                        onSubmit={handleSubmit}
                        submitLabel={sending ? 'Working…' : 'Send'}
                      />

                      {runErrorMessage ? (
                        <section className="inline-notice error">
                          {runErrorMessage}
                        </section>
                      ) : null}
                    </section>
                  )}
                </>
              )}
            </section>

            {showShortlistDrawer ? (
              <button
                aria-label="Close schemes panel"
                className="shortlist-backdrop mobile-only"
                onClick={() => setShowShortlistDrawer(false)}
                type="button"
              />
            ) : null}

            <aside
              className={`scheme-discovery-panel ${showShortlistDrawer ? 'is-open' : ''} ${
                !shortlist.length ? 'is-empty' : ''
              }`}
            >
              <div className="shortlist-panel-header">
                <div>
                  <h2>Suggested matches</h2>
                  <p>
                    {shortlist.length
                      ? 'Top schemes for your context and current query.'
                      : 'No grounded shortlist is available for this turn yet.'}
                  </p>
                </div>
                <div className="shortlist-panel-actions">
                  <span className="count-pill">{shortlist.length}</span>
                  <button
                    aria-label="Close schemes panel"
                    className="quiet-icon-button mobile-only"
                    onClick={() => setShowShortlistDrawer(false)}
                    type="button"
                  >
                    <UiIcon name="plus" style={{ transform: 'rotate(45deg)' }} />
                  </button>
                </div>
              </div>

              {shortlist.length ? (
                <>
                  <div className="shortlist-list">
                    {shortlist.map((scheme, index) => (
                      <article
                        key={scheme.scheme_id}
                        className={`shortlist-card ${
                          selectedSchemeId === scheme.scheme_id ? 'is-selected' : ''
                        }`}
                        onClick={() => setSelectedSchemeId(scheme.scheme_id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            setSelectedSchemeId(scheme.scheme_id)
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="shortlist-rank">{index + 1}</div>
                        <div className="shortlist-card-body">
                          <div className="shortlist-card-copy">
                            <h3>
                              {getPrimarySchemeUrl(scheme) ? (
                                <a
                                  className="scheme-name-link"
                                  href={getPrimarySchemeUrl(scheme) ?? undefined}
                                  onClick={(event) => event.stopPropagation()}
                                  rel="noreferrer"
                                  target="_blank"
                                >
                                  {scheme.name ?? 'Unnamed scheme'}
                                </a>
                              ) : (
                                scheme.name ?? 'Unnamed scheme'
                              )}
                            </h3>
                            {buildSchemeMetaLine(scheme) ? (
                              <p className="shortlist-meta-line">
                                {buildSchemeMetaLine(scheme)}
                              </p>
                            ) : null}
                          </div>
                          <p>{scheme.summary}</p>
                          <div className="tag-row">
                            {scheme.tags.map((tag) => (
                              <span key={`${scheme.scheme_id}-${tag}`} className="tag">
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                        <span
                          className={`match-badge ${
                            scheme.matchLabel === 'High Match'
                              ? 'high'
                              : scheme.matchLabel === 'Medium Match'
                                ? 'medium'
                                : 'low'
                          }`}
                        >
                          {scheme.matchLabel}
                        </span>
                      </article>
                    ))}
                  </div>

                  <button className="wide-ghost-button" type="button">
                    View all schemes
                    <UiIcon name="external" />
                  </button>

                  <div className="shortlist-browse-card">
                    <UiIcon name="grid" />
                    <div>
                      <strong>Prefer to browse everything?</strong>
                      <p>Explore the complete scheme catalog across ministries and states.</p>
                    </div>
                  </div>

                  {selectedScheme ? (
                    <section className="scheme-detail-card">
                      <div className="scheme-detail-header">
                        <div>
                          <p className="section-kicker">Selected scheme</p>
                          <h3>
                            {getPrimarySchemeUrl(selectedScheme) ? (
                              <a
                                className="scheme-name-link"
                                href={getPrimarySchemeUrl(selectedScheme) ?? undefined}
                                rel="noreferrer"
                                target="_blank"
                              >
                                {selectedScheme.name}
                              </a>
                            ) : (
                              selectedScheme.name
                            )}
                          </h3>
                          {buildSchemeMetaLine(selectedScheme) ? (
                            <p className="shortlist-meta-line">
                              {buildSchemeMetaLine(selectedScheme)}
                            </p>
                          ) : null}
                        </div>
                        <span
                          className={`match-badge ${
                            selectedScheme.matchLabel === 'High Match'
                              ? 'high'
                              : selectedScheme.matchLabel === 'Medium Match'
                                ? 'medium'
                                : 'low'
                          }`}
                        >
                          {selectedScheme.matchLabel}
                        </span>
                      </div>

                      {selectedScheme.retrieval_reason ? (
                        <p className="scheme-detail-summary">
                          {selectedScheme.retrieval_reason}
                        </p>
                      ) : null}

                      <ExpandableMarkdownSection
                        content={selectedScheme.details}
                        label="Overview"
                      />
                      <ExpandableMarkdownSection
                        content={selectedScheme.benefits}
                        label="Benefits"
                      />
                      <ExpandableMarkdownSection
                        content={selectedScheme.eligibility}
                        label="Eligibility"
                      />
                      <ExpandableMarkdownSection
                        content={selectedScheme.documents_required}
                        label="Documents required"
                      />

                      {getDisplaySourceLinks(selectedScheme).length ? (
                        <div className="scheme-link-list">
                          {getDisplaySourceLinks(selectedScheme).map((source) => (
                            <a
                              key={`${source.url}-${source.text ?? 'source'}`}
                              className="scheme-link"
                              href={source.url}
                              rel="noreferrer"
                              target="_blank"
                            >
                              <span>{source.text ?? source.url}</span>
                              <UiIcon name="external" />
                            </a>
                          ))}
                        </div>
                      ) : null}
                    </section>
                  ) : null}
                </>
              ) : (
                <section className="inline-notice">
                  No real scheme shortlist was retrieved for this turn. When a grounded
                  retrieval run succeeds, the matched schemes will appear here.
                </section>
              )}
            </aside>
          </div>
        </div>
      </section>
    </main>
  )
}

function SidebarNavItem({
  active = false,
  badge,
  icon,
  label,
}: {
  active?: boolean
  badge?: string
  icon: Parameters<typeof UiIcon>[0]['name']
  label: string
}) {
  return (
    <div className={`sidebar-nav-item ${active ? 'is-active' : ''}`}>
      <UiIcon className="sidebar-nav-icon" name={icon} />
      <span>{label}</span>
      {badge ? <span className="count-pill">{badge}</span> : null}
    </div>
  )
}

function ComposerCard({
  composer,
  composerFormRef,
  composerRef,
  disabled,
  helperText,
  onChange,
  onKeyDown,
  onSubmit,
  submitLabel,
}: {
  composer: string
  composerFormRef: React.RefObject<HTMLFormElement | null>
  composerRef: React.RefObject<HTMLTextAreaElement | null>
  disabled: boolean
  helperText: string
  onChange: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  submitLabel: string
}) {
  return (
    <form className="premium-composer" onSubmit={onSubmit} ref={composerFormRef}>
      <label className="composer-label" htmlFor="message">
        Message
      </label>

      <div className="composer-frame">
        <textarea
          id="message"
          ref={composerRef}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about your situation, eligibility, education, business, health, or support..."
          rows={1}
          value={composer}
        />

        <div className="composer-toolbar">
          <div className="composer-toolbar-left">
            <button className="composer-chip" disabled type="button">
              <UiIcon name="attach" />
              Attach
            </button>
          </div>

          <div className="composer-toolbar-right">
            <span className="composer-hint">{helperText}</span>
            <div className="composer-action-cluster">
              <button
                aria-label="Use microphone"
                className="quiet-icon-button composer-voice-button"
                disabled
                type="button"
              >
                <UiIcon name="microphone" />
              </button>
              <button
                className="send-fab"
                disabled={disabled || !composer.trim()}
                type="submit"
              >
                <UiIcon name="send" />
                <span className="sr-only">{submitLabel}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </form>
  )
}

function ChatMessageBubble({ message }: { message: ChatMessageRecord }) {
  const isAssistant = message.role === 'assistant'

  return (
    <article className={`chat-message ${isAssistant ? 'is-assistant' : 'is-user'}`}>
      <div className="chat-message-meta">
        <div className="chat-message-author">
          {isAssistant ? <BrandCrest className="mini-crest" /> : <span className="avatar-dot">Y</span>}
          <span>{isAssistant ? 'JurisAI' : 'You'}</span>
        </div>
        <span>{formatMessageTime(message.created_at)}</span>
      </div>

      <div className={`chat-message-bubble ${isAssistant ? 'assistant' : 'user'}`}>
        {isAssistant ? (
          <MarkdownBlock className="markdown-content" content={message.content} />
        ) : (
          <p className="message-plain">{message.content}</p>
        )}
      </div>
    </article>
  )
}

function LiveAssistantBubble({
  draftAnswer,
  errorMessage,
  expanded,
  onToggleExpanded,
  stageLog,
}: {
  draftAnswer: string
  errorMessage: string | null
  expanded: boolean
  onToggleExpanded: () => void
  stageLog: StageEntry[]
}) {
  const latestStageIndex = stageLog.length - 1
  const latestStage = stageLog.at(-1)
  const latestStageContent = latestStage
    ? describeStageEntry(latestStage)
    : {
        label: 'Thinking',
        detail: 'Preparing your grounded response.',
      }
  const canExpand = stageLog.length > 1

  return (
    <article className="chat-message is-assistant">
      <div className="chat-message-meta">
        <div className="chat-message-author">
          <BrandCrest className="mini-crest" />
          <span>JurisAI</span>
        </div>
        <span>Live</span>
      </div>

      <div className="chat-message-bubble assistant live-bubble">
        <div aria-live="polite" className="live-progress-shell">
          <button
            aria-expanded={canExpand ? expanded : false}
            className={`live-progress-card ${expanded ? 'is-expanded' : ''} ${
              errorMessage ? 'is-error' : ''
            }`}
            onClick={canExpand ? onToggleExpanded : undefined}
            type="button"
          >
            <span className="live-stage-dot" />
            <div className="live-progress-copy">
              <strong>{latestStageContent.label}</strong>
              <span>{latestStageContent.detail}</span>
            </div>
            <span className="live-progress-toggle">
              {canExpand ? (expanded ? 'Hide steps' : 'Show steps') : 'Live'}
            </span>
          </button>

          {expanded ? (
            <div className="live-stage-list">
              {stageLog.map((entry, index) => {
                const describedEntry = describeStageEntry(entry)
                return (
                  <div
                    key={`${entry.stage}-${index}`}
                    className={`live-stage-item ${
                      index === latestStageIndex ? 'is-active' : 'is-complete'
                    }`}
                  >
                    <span className="live-stage-dot" />
                    <div>
                      <strong>{describedEntry.label}</strong>
                      <span>{describedEntry.detail}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>

        {draftAnswer.trim() ? (
          <div className="streamed-answer">
            <MarkdownBlock className="markdown-content" content={draftAnswer} />
          </div>
        ) : errorMessage ? null : (
          <p className="message-pending">Preparing grounded answer…</p>
        )}

        {errorMessage ? <section className="inline-notice error">{errorMessage}</section> : null}
      </div>
    </article>
  )
}

function ExpandableMarkdownSection({
  content,
  label,
}: {
  content?: string | null
  label: string
}) {
  const trimmedContent = content?.trim()
  const [expanded, setExpanded] = useState(false)

  if (!trimmedContent) {
    return null
  }

  const canCollapse = trimmedContent.length > COLLAPSE_PREVIEW_LENGTH

  return (
    <section className="detail-section">
      <div className="detail-section-header">
        <h4>{label}</h4>
        {canCollapse ? (
          <button
            className="inline-link-button"
            onClick={() => setExpanded((current) => !current)}
            type="button"
          >
            {expanded ? 'Less' : 'More'}
          </button>
        ) : null}
      </div>
      <div className={`detail-section-body ${canCollapse && !expanded ? 'is-collapsed' : ''}`}>
        <MarkdownBlock className="markdown-content" content={trimmedContent} />
      </div>
    </section>
  )
}

function MarkdownBlock({
  className,
  content,
}: {
  className?: string
  content: string
}) {
  return (
    <div className={className}>
      <ReactMarkdown
        components={{
          a: ({ ...props }) => <a {...props} rel="noreferrer" target="_blank" />,
        }}
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function friendlyStageLabel(stage: string): string {
  return (
    FRIENDLY_STAGE_LABELS[stage] ??
    stage
      .split('_')
      .filter(Boolean)
      .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
      .join(' ')
  )
}

function describeStageEntry(entry: StageEntry): { label: string; detail: string } {
  switch (entry.stage) {
    case 'run_started':
      return {
        label: friendlyStageLabel(entry.stage),
        detail: 'Starting a grounded run for this request.',
      }
    case 'intent_classified': {
      const match = entry.detail.match(/^(.*?) \(confidence=([\d.]+)\)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: entry.detail }
      }
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Detected intent: ${match[1]} (${Math.round(Number(match[2]) * 100)}% confidence).`,
      }
    }
    case 'decision_made': {
      const match = entry.detail.match(/^(.*?) via (.*)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: entry.detail }
      }
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Next step: ${humanizeToken(match[1])} using ${humanizeToken(match[2])}.`,
      }
    }
    case 'retrieval_planned':
      return {
        label: friendlyStageLabel(entry.stage),
        detail: entry.detail.replace('tool call(s) selected', 'retrieval tool(s) selected.'),
      }
    case 'retrieval_started': {
      const match = entry.detail.match(/^(.+?) with query=(.+)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: entry.detail }
      }
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Running ${humanizeToken(match[1])} for ${match[2]}.`,
      }
    }
    case 'retrieval_completed': {
      const match = entry.detail.match(/^(\d+) schemes \(ignored_filters=(.+)\)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: entry.detail }
      }
      const ignoredFilters =
        match[2] === '[]'
          ? 'No important filters were ignored.'
          : `Ignored filters: ${match[2]}.`
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Reviewed ${match[1]} candidate schemes. ${ignoredFilters}`,
      }
    }
    case 'artifact_ready':
      return {
        label: friendlyStageLabel(entry.stage),
        detail: entry.detail.replace('scheme(s)', 'scheme shortlist item(s)'),
      }
    case 'response_generated':
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Drafting the final answer with ${humanizeToken(entry.detail)}.`,
      }
    default:
      return { label: friendlyStageLabel(entry.stage), detail: entry.detail }
  }
}

function mapShortlist(
  schemes: TopSchemeArtifactEntry[] | null | undefined,
  options?: { includeDemoFallback?: boolean },
): ShortlistScheme[] {
  if (!schemes?.length) {
    return options?.includeDemoFallback ? DEMO_SHORTLIST : []
  }

  return schemes.map((scheme, index) => ({
    ...scheme,
    matchLabel: index < 2 ? 'High Match' : index < 4 ? 'Medium Match' : 'Low Match',
    summary: buildSchemeSummary(scheme),
    tags: buildSchemeTags(scheme),
  }))
}

function buildSchemeMetaLine(scheme: TopSchemeArtifactEntry): string | null {
  const parts = [scheme.provider, scheme.ministry, scheme.state].filter(Boolean) as string[]
  if (!parts.length) {
    return null
  }

  return Array.from(new Set(parts)).join(' · ')
}

function buildFollowUpChips(selectedScheme: ShortlistScheme | null): string[] {
  if (!selectedScheme?.name) {
    return ['Eligibility details', 'How to apply', 'Documents required']
  }

  const firstWord = selectedScheme.name.split(' ')[0]
  return [
    `Eligibility for ${firstWord}`,
    `How to apply for ${firstWord}`,
    'Schemes for rural women',
  ]
}

function buildWorkflowSteps(stageLog: StageEntry[]) {
  if (!stageLog.length) {
    return DEFAULT_WORKFLOW_STEPS
  }

  const mapped = stageLog.map((entry, index) => ({
    label: describeStageEntry(entry).label,
    status:
      index === stageLog.length - 1
        ? ('active' as const)
        : ('complete' as const),
  }))

  return [
    ...mapped,
    { label: 'Grounding with official sources', status: 'pending' as const },
    { label: 'Drafting the answer', status: 'pending' as const },
  ].slice(0, 7)
}

function getConversationTitle(transcript: ChatMessageRecord[]): string {
  const firstUserMessage = transcript.find((message) => message.role === 'user')?.content?.trim()
  if (!firstUserMessage) {
    return 'Conversation'
  }

  return firstUserMessage.length > 44
    ? `${firstUserMessage.slice(0, 44).trim()}…`
    : firstUserMessage
}

function formatMessageTime(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return date.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })
}
