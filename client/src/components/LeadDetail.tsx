import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import type { ChatMessage, LeadDetailData, MessagesResponse } from '../lib/types'
import { clock, humanize, toText } from '../lib/format'
import { HandoffChip, OptedOutChip, ScoreBadge, StatusChip } from './Badges'
import KeyValues from './KeyValues'
import ProfilePanel from './ProfilePanel'

type Props = {
  contactId: string
  onBack: () => void
  onChanged: () => void
}

function describeSendError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.message.startsWith('window_expired')) {
      return 'More than 24 hours have passed since the customer last wrote, so a free-form reply is not allowed. A template message is needed (templates are not built yet).'
    }
    return err.message
  }
  return 'Could not send the message. Please try again.'
}

function Bubble({ m }: { m: ChatMessage }) {
  const fromClient = m.direction === 'in'
  const fromHuman = !fromClient && m.sender === 'human'
  const toolText = m.tool_used ? toText(m.tool_used) : ''

  const wrap = fromClient ? 'items-start' : 'items-end'
  const bubble = fromClient
    ? 'bg-white border border-charcoal-200 text-charcoal-950'
    : fromHuman
      ? 'bg-charcoal-800 text-white'
      : 'bg-brand-100 text-charcoal-950'
  const label = fromClient ? 'Customer' : fromHuman ? 'Team' : 'AI'

  return (
    <div className={`flex flex-col ${wrap}`}>
      <div className={`max-w-[85%] rounded-lg px-3 py-2 ${bubble}`}>
        <div className={`mb-0.5 text-xs font-medium ${fromHuman ? 'text-charcoal-200' : 'text-charcoal-600'}`}>
          {label}
        </div>
        <p className="whitespace-pre-wrap break-words">{m.content}</p>
        {toolText && (
          <details className="mt-1 text-xs text-charcoal-600">
            <summary className="cursor-pointer">Tool used</summary>
            <span className="break-words">{toolText}</span>
          </details>
        )}
      </div>
      <span className="mt-0.5 text-xs text-charcoal-400">{clock(m.created_at)}</span>
    </div>
  )
}

export default function LeadDetail({ contactId, onBack, onChanged }: Props) {
  const { user } = useAuth()

  const [detail, setDetail] = useState<LeadDetailData | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [messagesLoaded, setMessagesLoaded] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)

  const [showProfile, setShowProfile] = useState(false)
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const pendingId = useRef<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    api<LeadDetailData>(`/leads/${contactId}`)
      .then((d) => {
        if (!cancelled) {
          setDetail(d)
          setDetailError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDetailError(
            err instanceof ApiError && err.status === 404
              ? 'This lead was not found, or it is not assigned to you.'
              : err instanceof ApiError
                ? err.message
                : 'Could not load this lead.',
          )
        }
      })
    return () => {
      cancelled = true
    }
  }, [contactId, tick])

  const conversationId = detail?.conversations[0]?.id ?? null

  const loadMessages = useCallback(async () => {
    if (!conversationId) return
    try {
      const r = await api<MessagesResponse>(`/conversations/${conversationId}/messages`)
      setMessages(r.items)
      setStatus(r.status)
      setMessagesError(null)
      setMessagesLoaded(true)
    } catch (err) {
      setMessagesError(err instanceof ApiError ? err.message : 'Could not load messages.')
    }
  }, [conversationId])

  useEffect(() => {
    if (!conversationId) return
    void loadMessages()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') void loadMessages()
    }, 5000)
    return () => clearInterval(timer)
  }, [conversationId, loadMessages])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length])

  const current = status ?? detail?.conversations[0]?.status ?? null
  const optedOut = detail?.consent_status === 'opted_out'
  const inHumanMode = current === 'human'

  async function act(kind: 'takeover' | 'release') {
    if (!conversationId) return
    setActing(true)
    setActionError(null)
    try {
      await api(`/conversations/${conversationId}/${kind}`, { method: 'POST' })
      await loadMessages()
      setTick((t) => t + 1)
      onChanged()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'That did not work. Please try again.')
    } finally {
      setActing(false)
    }
  }

  async function send(e?: FormEvent) {
    e?.preventDefault()
    const body = text.trim()
    if (!body || sending || !conversationId) return
    setSendError(null)
    setSending(true)
    // The same id is reused on retry until the message goes through, so it can never send twice.
    if (!pendingId.current) pendingId.current = crypto.randomUUID()
    try {
      await api(`/conversations/${conversationId}/messages`, {
        body: { text: body, client_message_id: pendingId.current },
      })
      pendingId.current = null
      setText('')
      await loadMessages()
      onChanged()
    } catch (err) {
      setSendError(describeSendError(err))
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send()
    }
  }

  if (detailError) {
    return (
      <div className="p-6">
        <button type="button" onClick={onBack} className="mb-3 text-sm font-medium text-brand-text md:hidden">
          ← Back to leads
        </button>
        <p role="alert" className="rounded-md border border-danger px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-danger">
            ✗
          </span>
          {detailError}
        </p>
      </div>
    )
  }

  if (!detail) return <p className="p-6 text-sm text-charcoal-600">Loading lead...</p>

  const composerLocked = optedOut || !inHumanMode || !conversationId
  const lockReason = optedOut
    ? 'Locked: this customer has opted out of messages.'
    : !conversationId
      ? 'There is no conversation with this lead yet.'
      : 'Take over to reply. Until then the AI handles this chat.'

  return (
    <div className="flex h-full min-h-0 w-full">
      <div className={`${showProfile ? 'hidden xl:flex' : 'flex'} min-w-0 flex-1 flex-col`}>
        <div className="flex items-center gap-2 border-b border-charcoal-200 bg-white p-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back to leads"
            className="h-10 w-10 shrink-0 rounded-md text-lg hover:bg-charcoal-50 md:hidden"
          >
            ←
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-semibold text-charcoal-950">{detail.name || detail.phone}</span>
              <ScoreBadge score={detail.lead_score} />
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-charcoal-600">{detail.phone}</span>
              <StatusChip status={current} />
              {detail.open_handoffs.length > 0 && <HandoffChip />}
              {optedOut && <OptedOutChip />}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowProfile(true)}
            className="h-10 rounded-md border border-charcoal-200 px-3 text-sm font-medium hover:bg-charcoal-50 xl:hidden"
          >
            Details
          </button>
          {conversationId &&
            (inHumanMode ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void act('release')}
                className="h-10 rounded-md border border-charcoal-600 px-3 text-sm font-medium text-charcoal-950 hover:bg-charcoal-50 disabled:opacity-50"
              >
                {acting ? 'Working...' : 'Hand back to agent'}
              </button>
            ) : (
              <button
                type="button"
                disabled={acting}
                onClick={() => void act('takeover')}
                className="h-10 rounded-md bg-brand-500 px-3 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
              >
                {acting ? 'Working...' : 'Take over'}
              </button>
            ))}
        </div>

        {actionError && (
          <p role="alert" className="mx-3 mt-3 rounded-md border border-danger bg-white px-3 py-2 text-sm">
            <span aria-hidden="true" className="mr-1 text-danger">
              ✗
            </span>
            {actionError}
          </p>
        )}

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-charcoal-50 p-4">
          {detail.open_handoffs.map((h) => (
            <div key={h.id} className="rounded-lg border-2 border-brand-500 bg-white p-3">
              <div className="text-sm font-semibold text-brand-text">Handoff: {humanize(h.reason)}</div>
              <div className="mt-2">
                <KeyValues data={h.summary} />
              </div>
            </div>
          ))}

          {messagesError && (
            <p role="alert" className="rounded-md border border-danger bg-white px-3 py-2 text-sm">
              <span aria-hidden="true" className="mr-1 text-danger">
                ✗
              </span>
              {messagesError}
            </p>
          )}
          {conversationId && !messagesLoaded && !messagesError && (
            <p className="text-sm text-charcoal-600">Loading messages...</p>
          )}
          {!conversationId && <p className="text-sm text-charcoal-600">No conversation with this lead yet.</p>}
          {messagesLoaded && messages.length === 0 && <p className="text-sm text-charcoal-600">No messages yet.</p>}
          {messages.map((m) => (
            <Bubble key={m.id} m={m} />
          ))}
          <div ref={endRef} />
        </div>

        <form onSubmit={(e) => void send(e)} className="border-t border-charcoal-200 bg-white p-3">
          {sendError && (
            <p role="alert" className="mb-2 rounded-md border border-danger px-3 py-2 text-sm">
              <span aria-hidden="true" className="mr-1 text-danger">
                ✗
              </span>
              {sendError}
            </p>
          )}
          {composerLocked && <p className="mb-2 text-sm text-charcoal-600">{lockReason}</p>}
          <div className="flex items-end gap-2">
            <label htmlFor="composer" className="sr-only">
              Reply to the customer
            </label>
            <textarea
              id="composer"
              rows={2}
              maxLength={4000}
              disabled={composerLocked || sending}
              value={text}
              onChange={(e) => {
                setText(e.target.value)
                pendingId.current = null
              }}
              onKeyDown={onKeyDown}
              placeholder={composerLocked ? 'Replies are off' : 'Type a reply. Enter sends, Shift+Enter adds a line.'}
              className="min-h-11 flex-1 resize-none rounded-md border border-charcoal-200 px-3 py-2 disabled:bg-charcoal-50 disabled:text-charcoal-400"
            />
            <button
              type="submit"
              disabled={composerLocked || sending || text.trim().length === 0}
              className="h-11 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>

      <aside
        aria-label="Lead profile"
        className={`${showProfile ? 'flex' : 'hidden xl:flex'} min-h-0 w-full flex-col overflow-y-auto border-l border-charcoal-200 bg-white xl:w-72 xl:shrink-0`}
      >
        <div className="flex items-center justify-between border-b border-charcoal-200 p-3 xl:hidden">
          <span className="font-semibold">Details</span>
          <button
            type="button"
            onClick={() => setShowProfile(false)}
            className="h-10 rounded-md border border-charcoal-200 px-3 text-sm font-medium hover:bg-charcoal-50"
          >
            Back to chat
          </button>
        </div>
        <ProfilePanel detail={detail} currentUserId={user?.id} />
      </aside>
    </div>
  )
}