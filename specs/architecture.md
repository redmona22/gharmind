# Architecture: Gharmind (AI Agent Platform for Real Estate)

Source: Real_Estate_AI_Agent_Build_Plan.docx, sections 4, 6, 7, 8, 10, 11

## 1. Assumptions

- One product serving many real estate companies (multi-tenant), covering sales and rentals.
- WhatsApp is the main channel.
- Built in code (not no-code) for control over security, logging, white-labelling and multi-tenancy.
- Data stored in an Indian region.

## 2. System overview

```
Buyer / Renter / Owner (WhatsApp, website, portals, ads)
            |
            v
Webhook gateway  ->  message queue
            |
            v
Agent service (LLM + tools + guardrails)
            |
            v
PostgreSQL (leads, listings, bookings, chats)  <->  Admin dashboard
            |
            v
Workers: follow-ups, reminders, calls, reports
            |
            v
Human salesperson (alerts, summaries, handoff)
```

## 3. Components

| Component | Responsibility |
| --- | --- |
| Webhook gateway | Verify signature, save raw event, enqueue, return 200 immediately |
| Message queue | Decouple intake from processing. At-least-once delivery. |
| Agent service | Conversation loop: load context, LLM decides, run tools, guardrails, send reply |
| Tool layer | Fixed set of code-defined tools. tenant_id injected by code. |
| Guardrail layer | Output checks (numbers, banned claims, data leaks), handoff triggers, rate limits, opt-out |
| PostgreSQL + pgvector | Source of truth, semantic search, row-level security |
| Redis | Queue backend, scheduler, rate limiting |
| Workers | Follow-ups, visit reminders, rental tasks, daily report, retries, retention jobs |
| Admin dashboard | Leads and conversations, listings, visits and reports |
| File storage | Photos, brochures, KYC, agreements (private, signed links) |
| Integrations | WhatsApp, Google Calendar, voice and telephony (later), payment gateway |

## 4. Technology stack

| Part | Choice |
| --- | --- |
| Backend | Python FastAPI (alternative: Node.js with NestJS) |
| Database | PostgreSQL with pgvector |
| Queue and scheduler | Redis with Celery (Python) or BullMQ (Node) |
| AI | Claude API with native tool calling. Smaller model (Haiku) for routine chats, stronger (Sonnet) for complex cases. Optional LangGraph for complex flows. |
| Channel | WhatsApp Business Cloud API directly, or via Gupshup / Interakt |
| Calendar | Google Calendar API |
| Voice (later) | Vapi or Retell plus Indian telephony (Exotel, Knowlarity) |
| Dashboard | React with Tailwind |
| File storage | S3-compatible |
| Hosting | Docker on AWS, DigitalOcean or similar, Indian region |
| Monitoring | Sentry, Grafana or a simple uptime monitor |

Confirm current pricing and features of WhatsApp, AI APIs and telephony before quoting any client.

## 5. Request flow (incoming message)

1. WhatsApp sends a webhook. Gateway verifies the signature.
2. Raw event saved, pushed to queue, `200` returned immediately.
3. Worker claims the idempotency key (wamid). Duplicate: stop.
4. Message saved in `messages`.
5. Agent loads contact profile and a short summary of past chats (not full history).
6. Router picks the mode (sales, rental, booking, documentation) and model (Haiku or Sonnet).
7. LLM either replies or calls a tool. Tools run in code, results return to the LLM.
8. Draft reply passes guardrails. If blocked, regenerate or hand off.
9. Reply sent (free-form inside 24-hour window, approved template outside).
10. Every message and tool call written to `audit_log`.

If the AI is unavailable: send "Thanks, our team will call you shortly" and alert a human.

## 6. Agent design

- **One unified assistant to the client, named Gharmind.** Internally four modes (sales, rental, booking, documentation) each with focused instructions.
- **Tools:** `search_listings`, `get_listing_details`, `calculate_emi`, `check_affordability`, `check_slots`, `book_visit`, `save_lead_info`, `schedule_followup`, `handoff_to_human`, `collect_document`, `screen_tenant`.
- **No free-form SQL, shell or web requests from the agent. Ever.**
- **Context:** contact profile plus summary of earlier chats. Minimum data to the model.
- **Cost control:** cached templates for common questions (location, amenities, payment plan), model routing, short context.

## 7. Multi-tenancy and isolation

- Every table has `tenant_id`; every query filters on it.
- PostgreSQL row-level security (RLS) enforces isolation in the database itself.
- Application sets the session tenant from the verified session or webhook mapping (phone number to tenant). Never from the LLM or user text.
- Automated tests attempt cross-tenant reads and must fail.
- No tenant's data is used for another tenant or for model training.

## 8. Idempotency design

Webhooks and jobs are delivered at least once. Every state-changing operation must be safe to run twice.

- `idempotency_keys` table, unique on `(tenant_id, key)`.
- Claim before work: insert with status `processing`, do the work, mark `done` with stored result.
- Stuck keys: timeout of a few minutes lets another worker retry.
- Side effect and key update in one transaction where possible.
- Tools (`book_visit`, `schedule_followup`, `handoff_to_human`) return the existing record on a repeat call.
- Keys expire after 7 to 30 days.
- Outbound API calls carry an `Idempotency-Key` header where supported.

Key per operation: wamid (incoming message); message ID + status (status updates); contact + listing + slot (visit); contact + follow-up type + scheduled time (follow-up); visit ID + reminder type (reminder); conversation ID + reason + open status (handoff); contact + document type + version (document); gateway payment ID (receipt).

## 9. Background workers

| Worker | Job |
| --- | --- |
| Follow-up engine | Every minute, send due follow-ups within WhatsApp rules |
| Visit reminders | One day before and two hours before each visit |
| Rental tasks | Rent reminders, renewal alerts, vacancy re-listing |
| Daily report | Leads, response time, visits, bookings to the company owner |
| Retries | Backoff, then alert |
| Retention and deletion | Apply retention schedule; "delete this person everywhere" workflow |

## 10. Security architecture

- MFA for all dashboard users. Role-based access (salesperson: own leads; admin: own company; platform: operator only).
- TLS in transit; encryption at rest (database, backups, storage); field-level encryption for ID numbers and income.
- Secrets in a secrets manager, rotated. PII masked in logs and Sentry.
- Private file storage with short-lived signed links. Uploads scanned for type and malware.
- Webhook and payment callback signatures verified.
- WAF and rate limiting in front of the API. Database and Redis on a private network.
- Separate staging and production, no real customer data in testing.
- Dependency and container scanning. Penetration test before first paying client.
- Logs kept at least 180 days in an Indian region (CERT-In).

### AI-specific security

- Prompt injection: user text, documents and tool results are data, never instructions.
- Fixed tool list, tenant_id set by code.
- Least data to the model (no full KYC or ID numbers unless a step requires it).
- Output checks: prices not in tool results, other customers' details, internal instructions, banned claims.
- Provider with no-training-on-customer-data terms, listed as a sub-processor.
- Red-team test set re-run after every prompt or model change.

## 11. Deployment

- Pilot: one modest machine running app, worker, Postgres and Redis (Docker Compose). Split when load demands.
- Region: Indian region for primary storage and logs.
- Daily encrypted backups stored separately; monthly restore test.
- Uptime monitoring and phone alerts.

## 12. Key decisions and rationale

| Decision | Reason |
| --- | --- |
| Code over no-code | Clients trust real engineering; control over security, logging, white-labelling, multi-tenancy |
| Claude with tool calling | Native tool use fits fixed-tool agent design |
| RLS in Postgres | Database refuses cross-tenant reads even if app code has a bug |
| Queue-first webhooks | Fast 200 responses prevent duplicate deliveries |
| Guardrails in code | The real risk is a wrong price or an unkeepable promise, not downtime |
| Phased delivery | Shipping everything at once yields ten things done badly |
