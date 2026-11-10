# Backend Spec: Gharmind (AI Agent Platform for Real Estate)

Source: Real_Estate_AI_Agent_Build_Plan.docx, sections 4 to 8, 10. Stack assumed: Python FastAPI, PostgreSQL + pgvector, Redis + Celery. Column lists beyond the plan are proposed starting points; adjust against the pilot client's real data.

## 1. Proposed project structure

```
backend/
  app/
    main.py                 # FastAPI app
    config.py               # settings from env / secrets manager
    api/
      webhooks/whatsapp.py  # verify, save raw, enqueue, 200
      webhooks/payments.py
      routes/               # dashboard API: leads, conversations, listings, visits, reports
    core/
      tenancy.py            # tenant resolution + RLS session setup
      auth.py               # login, MFA, roles
      idempotency.py        # claim / complete / expire keys
      audit.py              # audit_log writer
      consent.py
    agent/
      loop.py               # conversation loop
      router.py             # mode + model routing
      prompts/              # sales, rental, booking, documentation
      tools/                # one file per tool
      guardrails/           # number check, banned claims, leak check, handoff rules
      summarizer.py         # old-chat summaries
    integrations/           # whatsapp, calendar, storage, voice (later), payments
    workers/                # followups, reminders, rentals, reports, retries, retention
    db/
      models.py
      migrations/
  tests/
    isolation/              # cross-tenant read attempts must fail
    idempotency/            # replay webhooks, kill worker, replay payment callback
    redteam/                # prompt injection and policy attack set
```

## 2. Database

Every table has `tenant_id`. Every query filters on it. Row-level security is enabled on every tenant table.

| Table | Purpose and key fields |
| --- | --- |
| tenants | Company, branding, settings, plan, WhatsApp number |
| users | Salespeople, admins, owners: role, assigned leads, MFA |
| contacts | Buyers, renters, owners: phone, language, source, lead score, consent status |
| listings | Type (sale/rent), project, price or rent, deposit, BHK, area, furnishing, tenant preference, status, RERA number, media links, embedding |
| conversations | One per contact and channel: status, assigned human, last activity |
| messages | direction, sender (client/agent/human), content, tool used, timestamp, wamid |
| visits | Contact, listing, time, status (booked/done/no-show), outcome |
| follow_ups | Scheduled message, channel, due time, status, stop condition |
| documents | KYC and agreement files: type, storage link, verification status |
| handoffs | Reason, summary, assigned salesperson, resolved or not |
| rentals | Active tenancies: tenant, owner, rent, due date, renewal date |
| idempotency_keys | key, tenant_id, operation, status (processing/done/failed), stored result, created time. Unique on (tenant_id, key) |
| audit_log | Every tool call and every number the agent quoted |

Additional supporting tables to add as needed: `consents` (exact wording, time, channel), `deletion_requests` (due date, status), `message_templates`, `approved_answers`.

### Constraints that matter

- `messages`: unique `(tenant_id, wamid)`.
- `idempotency_keys`: unique `(tenant_id, key)`.
- `listings`: sale listings require `rera_number`. Reject or flag status "promotable" without it.
- Sensitive fields (ID numbers, income) use field-level encryption.
- No card or bank details stored. Keep only the gateway reference ID.
- Aadhaar: never store the full number. Masked copy only, after legal advice.

## 3. API surface

### Webhooks

| Endpoint | Behaviour |
| --- | --- |
| `GET /webhooks/whatsapp` | Meta verification handshake |
| `POST /webhooks/whatsapp` | Verify signature, resolve tenant from receiving number, save raw event, enqueue, return 200 fast |
| `POST /webhooks/payments` | Verify signature, enqueue, record once by gateway payment ID |
| `POST /webhooks/leads/{source}` | Google, Facebook, portal lead forms (later) |

### Dashboard API (version 1)

- **Leads and conversations:** list/filter leads, read conversation, see score, take over manually, release back to agent
- **Listings:** CRUD, Excel import, media upload
- **Visits and reports:** calendar view, conversion numbers, cost per qualified lead by source
- **Auth:** login, MFA, roles, offboarding (instant access removal)
- **Privacy:** consent records, data export, correction, deletion request

## 4. Agent tools

tenant_id is injected by code from the verified session. It is never a tool parameter the LLM can set.

| Tool | Behaviour | Idempotent |
| --- | --- | --- |
| `search_listings(filters)` | Query live inventory by budget, area, BHK, type | read-only |
| `get_listing_details(id)` | Verified price, availability, RERA number, media | read-only |
| `calculate_emi(amount, rate, years)` | Deterministic EMI math | read-only |
| `check_affordability(income, emis)` | Realistic budget and loan eligibility estimate | read-only |
| `check_slots(date)` | Salesperson or owner availability | read-only |
| `book_visit(contact, listing, time)` | Create visit + calendar event + schedule reminders | yes: contact + listing + slot |
| `save_lead_info(fields)` | Store qualification answers, update score | yes |
| `schedule_followup(when, message)` | Add timed follow-up | yes: contact + type + time |
| `handoff_to_human(reason, summary)` | Alert salesperson with summary | yes: conversation + reason + open status |
| `collect_document(type)` | Request and record KYC or agreement doc | yes: contact + type + version |
| `screen_tenant(contact)` | Collect tenant details, build owner summary | yes |

Tool results are the only allowed source of prices, availability and numbers in replies.

## 5. Conversation loop

1. Message arrives and is saved (idempotent on wamid).
2. Load contact profile and a short summary of old chats.
3. Router selects mode and model.
4. LLM replies directly or calls a tool. Tools run in code. Results go back to the LLM.
5. Draft reply goes through guardrails (see `rules.md`). On failure: regenerate, then hand off.
6. Reply sent per WhatsApp window rules. Write audit entries.
7. If the AI call fails: fallback message and human alert.

### Handoff triggers (code, not prompt)

Discount or negotiation or final price; "I'm interested" or visit request; hesitation or competitor comparison; lead score over threshold; any legal question or complaint; user says they are under 18.

## 6. Guardrail implementation points

- **Number check:** extract every number from the draft reply. Each must appear in this turn's tool results (or be a trivial value like a date the agent was given). Otherwise block and regenerate.
- **Banned claims:** pattern and semantic check for "guaranteed returns", "best investment" and similar.
- **Leak check:** block other customers' details and internal instructions.
- **Rate limits:** per contact, to stop loops and abuse.
- **Opt-out:** "stop" ends all messaging immediately; flag contact; cancel pending follow-ups.
- **Promotion block:** no promotion of a sale project without a RERA number.

## 7. Workers

| Worker | Schedule | Notes |
| --- | --- | --- |
| Follow-up engine | Every minute | Free-form inside 24-hour window; approved templates outside. Mark sent in same transaction as send record. |
| Visit reminders | Day before and 2 hours before | One row per (visit, reminder type) |
| Rental tasks | Daily | Rent reminders, renewal alerts, vacancy re-listing |
| Daily report | Daily | Leads, response time, visits, bookings to owner |
| Retries | On failure | Exponential backoff, then alert |
| Retention | Daily | Apply retention schedule; process deletion requests |
| Stuck-key reaper | Every few minutes | Release `processing` keys past timeout |
| Key cleanup | Daily | Expire keys older than 7 to 30 days |

## 8. Idempotency implementation

1. Respond to webhooks fast: save raw event, enqueue, return 200.
2. Unique constraint on `(tenant_id, key)` is the real guard. App checks alone can race.
3. Claim before work: insert key as `processing`; on conflict read existing row.
   - `done`: return stored result.
   - `processing`: wait or exit.
4. Do the work, then mark `done` and store result, in the same transaction as the side effect where possible.
5. Timeout for stuck `processing` keys lets another worker retry.
6. Outbound calls: generate key once per operation and send as `Idempotency-Key`.

### Required tests

- Same webhook sent five times leaves exactly one result.
- Worker killed mid-job leaves exactly one result after retry.
- Replayed payment callback records once.
- LLM calls the same tool twice and gets the same record.

## 9. Retention and deletion

| Data | Keep | Then |
| --- | --- | --- |
| Unconverted leads and chats | ~12 months after last activity | Delete or anonymise |
| Call recordings | 30 to 90 days | Delete, keep text summary |
| KYC documents | Until deal/tenancy closes plus client's legal period | Delete and log |
| Agreements and receipts | Per client's legal and tax duties | Archive, then delete |
| System and security logs | At least 180 days (Indian region) | Delete |
| Consent and deletion records | Long enough to prove compliance | Minimal proof only |

Build a scheduled job for these rules and a "delete this person everywhere" function that clears backups on next rotation and informs sub-processors. Each client and its lawyer confirm final periods.

## 10. Configuration and secrets

- Secrets (WhatsApp token, Claude API key, calendar credentials, gateway keys) in a secrets manager. Never in code or logs. Rotate regularly.
- Environment-specific settings for staging vs production. No real customer data in staging.
- Per-tenant settings: branding, WhatsApp number, handoff thresholds, languages, working hours, approved answers.

## 11. Observability

- Sentry with PII masking.
- Structured logs of every conversation and tool call (audit_log).
- Alerts: unusual logins, mass export, failed webhook signatures, error spikes, stuck queues.
- Uptime monitor with phone alerts.
- Logs retained at least 180 days in India.
