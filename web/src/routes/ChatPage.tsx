import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight } from '@phosphor-icons/react'
import { createFixtureArtifact, createFixtureSession, FIXTURE_ANSWER } from '../fixtures'
import type { FormEvent, KeyboardEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { createMessage, getSession } from '../api'
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

const COLLAPSE_PREVIEW_LENGTH = 360

const FRIENDLY_STAGE_LABELS: Record<string, string> = {
  run_started: 'Thinking',
  intent_classified: 'Understanding your request',
  decision_made: 'Planning the next step',
  retrieval_planned: 'Preparing search tools',
  retrieval_started: 'Searching schemes',
  retrieval_completed: 'Reviewing retrieved schemes',
  artifact_ready: 'Schemes ready',
  response_generated: 'Finalizing answer',
}

const STARTER_PROMPTS = [
  'Which schemes are relevant for a woman entrepreneur starting a small business in Maharashtra?',
  'My family needs support for healthcare and insurance. Which government schemes should we consider?',
  'I am a student from a low-income household. What scholarships or education schemes may apply?',
]

type ChatLocationState = {
  initialPrompt?: string
  autoSubmit?: boolean
}

export function ChatPage() {
  const { sessionId = '' } = useParams()
  const fixtureMode = import.meta.env.DEV && new URLSearchParams(window.location.search).get('fixture') === '1'
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
  const [lastPrompt, setLastPrompt] = useState('')
  const eventSourceRef = useRef<EventSource | null>(null)
  const initialPromptAppliedRef = useRef(false)
  const startMessageRef = useRef<(message: string, sessionOverride?: ChatSessionRecord) => Promise<void>>(async () => {})
  const composerFormRef = useRef<HTMLFormElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const messageScrollAreaRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadSession() {
      setLoading(true)
      try {
        const response = fixtureMode
          ? { session: createFixtureSession(sessionId) }
          : await getSession(sessionId)
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
        const locationState = location.state as ChatLocationState | null
        const initialPrompt = locationState?.initialPrompt?.trim()
        if (!initialPromptAppliedRef.current && initialPrompt) {
          initialPromptAppliedRef.current = true
          if (locationState?.autoSubmit) void startMessageRef.current(initialPrompt, response.session)
          else setComposer(initialPrompt)
        }
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
  }, [sessionId, location.state, fixtureMode])


  useEffect(() => {
    const composerElement = composerRef.current
    if (!composerElement) {
      return
    }

    composerElement.style.height = 'auto'
    composerElement.style.height = `${Math.min(composerElement.scrollHeight, 240)}px`
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
  const schemeCount = currentArtifact?.schemes.length ?? 0
  const showArtifacts = schemeCount > 0
  const showLiveAssistant =
    sending ||
    Boolean(draftAnswer.trim()) ||
    Boolean(runErrorMessage) ||
    stageLog.length > 0

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await startMessage(composer.trim())
  }

  async function startMessage(message: string, sessionOverride?: ChatSessionRecord) {
    const activeSession = sessionOverride ?? session
    if (!message || !activeSession || sending) return

    setLastPrompt(message)
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
      if (fixtureMode) {
        const long = new URLSearchParams(window.location.search).get('long') === '1'
        const shouldFail = new URLSearchParams(window.location.search).get('fail') === '1'
        const events: StageEntry[] = [
          { stage: 'run_started', detail: 'Starting.' },
          { stage: 'intent_classified', detail: 'agriculture (confidence=0.92)' },
          { stage: 'retrieval_started', detail: 'semantic_search with query=farmer crop support' },
          { stage: 'retrieval_completed', detail: '5 schemes (ignored_filters=[])' },
          { stage: 'artifact_ready', detail: '5 scheme(s) ready to review' },
        ]
        for (const event of events) {
          await new Promise(resolve => window.setTimeout(resolve, 420))
          setStageLog(current => [...current, event])
          if (event.stage === 'artifact_ready') setCurrentArtifact(createFixtureArtifact(activeSession.session_id))
        }
        if (shouldFail) {
          setRunErrorMessage('The fixture run was interrupted. You can retry this preserved message.')
          setStageHistoryExpanded(true)
        } else {
          const answer = long ? `${FIXTURE_ANSWER}\n\n${FIXTURE_ANSWER}\n\n${FIXTURE_ANSWER}` : FIXTURE_ANSWER
          for (let i = 0; i < answer.length; i += 13) {
            await new Promise(resolve => window.setTimeout(resolve, 18))
            setDraftAnswer(current => current + answer.slice(i, i + 13))
          }
          setStageHistoryExpanded(false)
        }
        setSending(false)
        return
      }

      const response = await createMessage(activeSession.session_id, message)
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
        setStageHistoryExpanded(true)
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
        setStageHistoryExpanded(true)
        setSending(false)
        source.close()
        eventSourceRef.current = null
      }
    } catch (error) {
      setSending(false)
      setRunErrorMessage(
        error instanceof Error ? error.message : 'Failed to send message.',
      )
      setStageHistoryExpanded(true)
    }
  }

  startMessageRef.current = startMessage

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
    <main className="chat-shell">
      <section className="chat-app-frame">
        <header className="topbar">
          <div className="brand-cluster">
            <Link className="brand-mark" to="/" aria-label="JurisAI home">J</Link>
            <div>
              <p className="eyebrow">JurisAI</p>
              <h1>{transcript.length ? 'Scheme guidance' : 'New conversation'}</h1>
            </div>
          </div>
          <div className="topbar-meta">
            <span className={`chip ${sending ? 'chip-live' : ''}`}>{statusLabel}</span>
            <Link className="ghost-link" to="/">
              New chat
            </Link>
          </div>
        </header>

        {loading ? (
          <section className="empty-state">Loading conversation…</section>
        ) : sessionErrorMessage ? (
          <section className="error-state">{sessionErrorMessage}</section>
        ) : (
          <section className="chat-grid">
            <section className="transcript-panel">
              <div className="panel-header">
                <div>
                  <p className="panel-kicker">Conversation</p>
                  <h2>
                    {transcript.length
                      ? 'Ask follow-ups naturally'
                      : 'Ask about eligibility, benefits, documents, or the best fit'}
                  </h2>
                </div>
                {sending ? (
                  <span className="chip subtle">
                    {latestStageDescription?.detail ?? 'Working on your request'}
                  </span>
                ) : null}
              </div>

              <div className="message-scroll-area" ref={messageScrollAreaRef}>
                <div className="message-list">
                  {transcript.length === 0 && !showLiveAssistant ? (
                    <section className="welcome-panel">
                      <div className="welcome-copy">
                        <p className="section-label">Start here</p>
                        <h3>Describe your situation in one message.</h3>
                        <p>
                          JurisAI can narrow by state, beneficiary type, benefits,
                          and follow-up constraints while keeping the conversation
                          straightforward.
                        </p>
                      </div>
                      <div className="starter-grid compact">
                        {STARTER_PROMPTS.map((prompt) => (
                          <button
                            key={prompt}
                            className="starter-card"
                            onClick={() => setComposer(prompt)}
                            type="button"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {transcript.map((message) => (
                    <ChatMessageBubble key={message.message_id} message={message} />
                  ))}

                  {showLiveAssistant ? (
                    <LiveAssistantBubble
                      draftAnswer={draftAnswer}
                      errorMessage={runErrorMessage}
                      onRetry={() => void startMessage(lastPrompt)}
                      expanded={stageHistoryExpanded}
                      onToggleExpanded={() => setStageHistoryExpanded((current) => !current)}
                      stageLog={stageLog}
                    />
                  ) : null}
                </div>
              </div>

              <form className="composer" onSubmit={handleSubmit} ref={composerFormRef}>
                <label className="composer-label" htmlFor="message">
                  Message
                </label>
                <div className="composer-shell">
                  <textarea
                    id="message"
                    ref={composerRef}
                    value={composer}
                    onChange={(event) => setComposer(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                    placeholder="Ask about schemes, eligibility, documents, benefits, or a follow-up..."
                    rows={1}
                    disabled={sending}
                  />
                  <div className="composer-actions">
                    <p className="helper-copy">
                      {sending
                        ? latestStageDescription?.detail ?? 'Preparing your answer'
                        : 'Enter sends. Shift+Enter adds a new line.'}
                    </p>
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={sending || !composer.trim()}
                    >
                      {sending ? 'Working…' : 'Send'}
                    </button>
                  </div>
                </div>
              </form>
            </section>

            {showArtifacts ? (
              <section className="inline-artifacts" aria-label="Retrieved schemes">
                <div className="artifact-heading"><span className="section-index">SCHEME MATCHES</span><span>{schemeCount} found</span></div>
                {(currentArtifact?.schemes ?? []).slice(0, 3).map(scheme => <SchemeCard key={scheme.scheme_id} scheme={scheme}/>) }
                {schemeCount > 3 ? <details className="more-schemes"><summary>Show {schemeCount - 3} more schemes</summary>{(currentArtifact?.schemes ?? []).slice(3).map(scheme => <SchemeCard key={scheme.scheme_id} scheme={scheme}/>)}</details> : null}
              </section>
            ) : null}
          </section>
        )}
      </section>
    </main>
  )
}

function ChatMessageBubble({ message }: { message: ChatMessageRecord }) {
  return (
    <article className={`message-bubble message-${message.role}`}>
      <p className="message-role">{message.role === 'assistant' ? 'JurisAI' : 'You'}</p>
      {message.role === 'assistant' ? (
        <MarkdownBlock className="message-content markdown-content" content={message.content} />
      ) : (
        <p className="message-content message-plain">{message.content}</p>
      )}
    </article>
  )
}

function LiveAssistantBubble({
  draftAnswer,
  errorMessage,
  onRetry,
  expanded,
  onToggleExpanded,
  stageLog,
}: {
  draftAnswer: string
  errorMessage: string | null
  onRetry: () => void
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
  const canExpand = stageLog.length > 0 || Boolean(errorMessage)

  return (
    <article className="message-bubble message-assistant message-live">
      <p className="message-role">JurisAI</p>

      <div aria-live="polite" className="live-progress-shell">
        <button
          aria-expanded={canExpand ? expanded : false}
          className={`live-progress-card ${expanded ? 'live-progress-card-expanded' : ''} ${
            errorMessage ? 'live-progress-card-error' : ''
          }`}
          onClick={canExpand ? onToggleExpanded : undefined}
          type="button"
        >
          <span className="stage-dot" />
          <div className="live-progress-copy">
            <p className="stage-label">{latestStageContent.label}</p>
            <p className="stage-detail">{latestStageContent.detail}</p>
          </div>
          <span className="live-progress-toggle">
            {canExpand ? (expanded ? 'Hide steps' : 'Show steps') : 'Live'}
          </span>
        </button>

        {expanded ? (
          <div className="stage-list">
            {stageLog.map((entry, index) => {
              const describedEntry = describeStageEntry(entry)
              return (
                <div
                  key={`${entry.stage}-${index}`}
                  className={`stage-item ${
                    index === latestStageIndex ? 'stage-item-active' : 'stage-item-complete'
                  }`}
                >
                  <span className="stage-dot" />
                  <div>
                    <p className="stage-label">{describedEntry.label}</p>
                    <p className="stage-detail">{describedEntry.detail}</p>
                  </div>
                </div>
              )
            })}
          </div>
        ) : null}

        {!stageLog.length ? (
          <div className="stage-list">
            <div
              className="stage-item stage-item-active"
            >
              <span className="stage-dot" />
              <div>
                <p className="stage-label">Thinking</p>
                <p className="stage-detail">Preparing your grounded response.</p>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {draftAnswer.trim() ? (
        <div className="streamed-answer">
          <MarkdownBlock className="message-content markdown-content" content={draftAnswer} />
        </div>
      ) : errorMessage ? null : (
        <p className="message-pending">Preparing grounded answer…</p>
      )}

      {errorMessage ? (
        <section className="inline-error live-error-block" aria-live="polite">
          <p className="stage-label">Response interrupted</p>
          <p className="stage-detail">{errorMessage}</p>
          <button className="inline-button" onClick={onRetry} type="button">Retry</button>
        </section>
      ) : null}
    </article>
  )
}

function SchemeCard({ scheme }: { scheme: TopSchemeArtifactEntry }) {
  const badgeLabel = getSchemeBadgeLabel(scheme)
  const meta = getSchemeMeta(scheme)

  return (
    <article className="scheme-card">
      <div className="scheme-header">
        <h3>{scheme.name ?? 'Unnamed scheme'}</h3>
        <span className="chip subtle chip-scheme">{badgeLabel}</span>
      </div>

      {meta ? <p className="scheme-meta">{meta}</p> : null}

      {scheme.retrieval_reason ? (
        <p className="scheme-highlight">{scheme.retrieval_reason}</p>
      ) : null}

      <div>
        <details className="scheme-details">
          <summary>View scheme details</summary>
          <div className="scheme-sections">
            <ExpandableMarkdownSection content={scheme.details} label="Details" />
            <ExpandableMarkdownSection content={scheme.eligibility} label="Eligibility" />
            <ExpandableMarkdownSection content={scheme.benefits} label="Benefits" />
            <ExpandableMarkdownSection content={scheme.documents_required} label="Documents required" />
          </div>
        </details>
        {scheme.url ? <a className="official-source" href={scheme.url} target="_blank" rel="noreferrer">Official source <ArrowUpRight size={15}/></a> : null}


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
    <section className="scheme-field">
      <div className="scheme-field-header">
        <h4>{label}</h4>
        {canCollapse ? (
          <button
            className="inline-button"
            onClick={() => setExpanded((current) => !current)}
            type="button"
          >
            {expanded ? 'Less' : 'More'}
          </button>
        ) : null}
      </div>
      <div className={`scheme-field-body ${canCollapse && !expanded ? 'collapsed' : ''}`}>
        <MarkdownBlock className="scheme-rich-text markdown-content" content={trimmedContent} />
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
        return { label: friendlyStageLabel(entry.stage), detail: "Reviewing your request and finding relevant scheme information." }
      }
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Detected intent: ${match[1]} (${Math.round(Number(match[2]) * 100)}% confidence).`,
      }
    }
    case 'decision_made': {
      const match = entry.detail.match(/^(.*?) via (.*)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: "Reviewing your request and finding relevant scheme information." }
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
        return { label: friendlyStageLabel(entry.stage), detail: "Reviewing your request and finding relevant scheme information." }
      }
      return {
        label: friendlyStageLabel(entry.stage),
        detail: `Running ${humanizeToken(match[1])} for ${match[2]}.`,
      }
    }
    case 'retrieval_completed': {
      const match = entry.detail.match(/^(\d+) schemes \(ignored_filters=(.+)\)$/)
      if (!match) {
        return { label: friendlyStageLabel(entry.stage), detail: "Reviewing your request and finding relevant scheme information." }
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
      return { label: friendlyStageLabel(entry.stage), detail: "Reviewing your request and finding relevant scheme information." }
  }
}

function humanizeToken(value: string): string {
  return value
    .replace(/^['"]|['"]$/g, '')
    .split('_')
    .filter(Boolean)
    .join(' ')
}

function getSchemeBadgeLabel(scheme: TopSchemeArtifactEntry): string {
  if (scheme.level === 'central') {
    return scheme.provider ?? scheme.ministry ?? 'Central ministry'
  }

  return scheme.state ?? scheme.provider ?? (scheme.level === 'state' ? 'State scheme' : 'General scheme')
}

function getSchemeMeta(scheme: TopSchemeArtifactEntry): string | null {
  if (scheme.level === 'central') {
    const ministryName = scheme.provider ?? scheme.ministry
    return ministryName ? `Provided by ${ministryName}` : 'Central government scheme'
  }

  const metaParts = [scheme.state ?? scheme.provider, scheme.level].filter(Boolean)
  return metaParts.length ? metaParts.join(' • ') : null
}
