# Tasks: Gharmind (AI Agent Platform for Real Estate)

Source: Real_Estate_AI_Agent_Build_Plan.docx, sections 13 to 15. Work phase by phase. Do not start a later phase until the earlier one works with real traffic. Tick items as they complete.

## Phase 0: Before writing code (start in parallel, long lead times)

- [ ] Apply for WhatsApp Business API access (business verification can take days or weeks)
- [ ] Find the pilot company with real lead volume
- [ ] Get a sample of the pilot company's real listings and lead sheets
- [ ] Write 30 to 50 real buyer and renter messages in Hindi, Odia and English as test cases
- [ ] Decide handoff rules together with the sales team
- [ ] Choose cloud provider and Indian region; confirm data-residency needs
- [ ] Decide backend: FastAPI (default) or NestJS
- [ ] Draft consent text and privacy policy (English, Hindi, Odia)
- [ ] Draft Data Processing Agreement and Master Service Agreement
- [ ] Book lawyer review of consent, contracts, rental and RERA flows (Odisha)
- [ ] Plan penetration test before launch
- [ ] Draft approved answer library and banned-claims list

## Phase 1: Core agent on WhatsApp (about 3 to 4 weeks)

### Foundation

- [ ] Repo, Docker Compose (app, worker, Postgres, Redis), CI, linting, tests
- [ ] Config and secrets handling
- [ ] Postgres schema: tenants, users, contacts, listings, conversations, messages, handoffs, idempotency_keys, audit_log, consents
- [ ] Row-level security on all tenant tables
- [ ] Tenant isolation tests (cross-tenant reads must fail)
- [ ] Auth with MFA and roles

### Webhook and queue

- [ ] WhatsApp webhook: verification handshake, signature check, save raw event, enqueue, 200
- [ ] Idempotency module (claim, complete, expire, stuck-key reaper)
- [ ] Idempotency tests (webhook x5, killed worker)
- [ ] Outbound WhatsApp sender with 24-hour window and template logic
- [ ] Opt-in capture and opt-out handling

### Agent

- [ ] Conversation loop with profile and chat summary
- [ ] Mode and model routing (Haiku / Sonnet)
- [ ] Tools: `search_listings`, `get_listing_details`, `calculate_emi`, `check_affordability`, `save_lead_info`, `handoff_to_human`
- [ ] Lead scoring v1
- [ ] Guardrails: number check, banned claims, leak check, rate limits, opt-out, RERA promotion block
- [ ] Handoff triggers and salesperson alert with summary
- [ ] Fallback holding message and human alert when AI is down
- [ ] Cached answers for common questions
- [ ] Red-team test set and run
- [ ] Hindi, Odia, English test cases passing

### Basic dashboard (React + Tailwind)

- [ ] Leads and conversations view (read chat, see score, take over)
- [ ] Listings view with manual add/edit
- [ ] Logging, Sentry (PII masked), uptime monitor

### Phase 1 exit

- [ ] Paid pilot started with agreed metrics
- [ ] Baseline numbers recorded (response time, leads answered, previously missed leads)

## Phase 2: Visits, follow-ups, import (about 2 to 3 weeks)

- [ ] visits and follow_ups tables
- [ ] Google Calendar integration
- [ ] Tools: `check_slots`, `book_visit`, `schedule_followup`
- [ ] Visit reminders (day before, 2 hours before)
- [ ] Reschedule handling and post-visit follow-up
- [ ] Follow-up engine worker (every minute, window and template rules)
- [ ] Idempotency for visits, follow-ups, reminders
- [ ] Excel import for listings
- [ ] Visits and reports view (calendar, conversion numbers, cost per qualified lead by source)
- [ ] Daily report to owner
- [ ] Retry with backoff and alerting

## Phase 3: Rentals (about 3 to 4 weeks)

- [ ] rentals and documents tables
- [ ] Owner listing intake
- [ ] Availability sync and owner visit-slot confirmation
- [ ] Tool: `screen_tenant`, `collect_document`
- [ ] Tenant screening summary for owner
- [ ] Agreement drafts (drafts only) and move-in checklist
- [ ] Police verification tracking where required (check Odisha rules)
- [ ] Deposit and rent receipts via traceable channels; payment webhook with idempotency
- [ ] Rent reminders, renewal alerts, maintenance requests
- [ ] Vacancy re-letting flow
- [ ] KYC storage: encrypted, signed links, malware scan, access log
- [ ] Rental-mode prompts and tests

## Phase 4: Voice, analytics, multi-tenant, billing (about 4 to 6 weeks)

- [ ] Voice calling (Vapi or Retell + Exotel or Knowlarity), AI disclosure at call start
- [ ] DLT registration, DND scrubbing, calling-hour limits
- [ ] Call recording retention rules
- [ ] Analytics: lead source, response time, visit-to-booking, salesperson performance, deal leakage
- [ ] Sales copilot: pre-call briefing, suggested replies, call list
- [ ] Marketing content generation with human review
- [ ] Multi-tenant onboarding flow and per-company branding
- [ ] Billing (setup fee, monthly fee, optional performance component)
- [ ] Owner portal, tenant and rent tracking views

## Cross-cutting: before first paying client

- [ ] Penetration test done and findings fixed
- [ ] Lawyer review complete
- [ ] DPA signed with the client; sub-processor list published
- [ ] Privacy policy and consent live in English, Hindi, Odia
- [ ] Retention and deletion jobs running; "delete this person everywhere" tested
- [ ] Incident response plan written; breach register started
- [ ] Encrypted backups with a successful restore test
- [ ] Logs retained 180+ days in an Indian region
- [ ] One-page security and privacy summary for sales
- [ ] Dependency and container scanning in CI
- [ ] Confirm current WhatsApp, AI and telephony pricing before quoting

## Go-to-market checkpoints

- [ ] Before and after numbers from pilot
- [ ] Pitch the next ten companies with those numbers
- [ ] Add follow-ups, rentals, owner handling only after the first piece works
- [ ] Move to monthly plans, then multi-tenant onboarding
