export type LastMessage = { sender: string; content: string; at: string }

export type LeadItem = {
  id: string
  name: string | null
  phone: string
  language: string | null
  source: string | null
  lead_score: number
  consent_status: string | null
  assigned_user_id: string | null
  conversation_id: string | null
  conversation_status: string | null
  last_message: LastMessage | null
  created_at: string
}

export type LeadListResponse = { items: LeadItem[]; total: number }

export type OpenHandoff = {
  id: string
  conversation_id: string
  reason: string
  summary: unknown
  created_at: string
}

export type LeadDetailData = {
  id: string
  name: string | null
  phone: string
  language: string | null
  source: string | null
  lead_score: number
  qualification: Record<string, unknown>
  consent_status: string | null
  assigned_user_id: string | null
  conversations: { id: string; status: string; channel: string }[]
  open_handoffs: OpenHandoff[]
}

export type ChatMessage = {
  id: string
  direction: string
  sender: string
  content: string
  tool_used: unknown
  created_at: string
}

export type MessagesResponse = {
  conversation_id: string
  status: string
  items: ChatMessage[]
}