export type ChatRole = 'user' | 'assistant'

export type SchemeRef = {
  scheme_id: string
  name?: string | null
  url?: string | null
  state?: string | null
  level?: string | null
  provider?: string | null
}

export type SchemeSource = {
  text?: string | null
  url?: string | null
}

export type EnrichedApplicationModes = {
  online?: string | null
  offline?: string | null
}

export type RelevantScheme = {
  scheme_id: string
  name?: string | null
  url?: string | null
  state?: string | null
  level?: string | null
  provider?: string | null
  provider_type?: string | null
  ministry?: string | null
  details?: string | null
  benefits?: string | null
  eligibility?: string | null
  documents_required?: string | null
  faq?: string | null
  application_modes?: EnrichedApplicationModes | null
  sources?: SchemeSource[]
  match_reasons?: string[]
}

export type TopSchemeArtifactEntry = {
  scheme_id: string
  name?: string | null
  url?: string | null
  state?: string | null
  level?: string | null
  provider?: string | null
  provider_type?: string | null
  ministry?: string | null
  details?: string | null
  benefits?: string | null
  eligibility?: string | null
  documents_required?: string | null
  faq?: string | null
  application_modes?: EnrichedApplicationModes | null
  references?: SchemeSource[]
  retrieval_reason?: string | null
}

export type TopSchemesArtifact = {
  artifact_id: string
  artifact_type: string
  chat_session_id: string
  turn_id: string
  schemes: TopSchemeArtifactEntry[]
}

export type SessionSnapshot = {
  chat_session_id?: string | null
  user_profile: Record<string, unknown>
  preferences: Record<string, unknown>
  last_user_goal?: string | null
  last_action?: string | null
  conversation_summary?: string | null
  active_constraints: Record<string, unknown>
  recent_scheme_refs: SchemeRef[]
  selected_scheme_ref?: SchemeRef | null
  relevant_schemes: RelevantScheme[]
  latest_top_schemes_artifact?: TopSchemesArtifact | null
}

export type ChatMessageRecord = {
  message_id: string
  role: ChatRole
  content: string
  turn_id?: string | null
  created_at: string
}

export type ChatSessionRecord = {
  session_id: string
  created_at: string
  updated_at: string
  session_snapshot: SessionSnapshot
  session_memory?: Record<string, unknown> | null
  messages: ChatMessageRecord[]
  artifacts: TopSchemesArtifact[]
}

export type CreateSessionResponse = {
  session: ChatSessionRecord
}

export type GetSessionResponse = {
  session: ChatSessionRecord
}

export type CreateMessageResponse = {
  run_id: string
  session_id: string
  status: 'queued' | 'running'
  stream_path: string
}

export type StreamEventMap = {
  run_started: {
    message: string
  }
  stage_update: {
    stage: string
    detail: string
  }
  answer_delta: {
    delta: string
  }
  artifact_ready: {
    artifact_type: string
    artifact_id: string
    artifact: TopSchemesArtifact
  }
  run_completed: {
    turn_id?: string | null
    assistant_message: string
    session: ChatSessionRecord
  }
  run_failed: {
    error: string
  }
}
