# PRD: Gharmind, the AI Agent Platform for Real Estate (Sales and Rentals)

Source: Real_Estate_AI_Agent_Build_Plan.docx (October 2026)

## 1. Summary

**Gharmind** is a multi-tenant platform that gives real estate companies one unified AI assistant. It answers every enquiry within seconds on WhatsApp (and later other channels), qualifies the person, matches live inventory to their budget, books site visits, follows up, and hands a ready-to-talk lead to a human salesperson. It covers both sales and rentals.

**Principle: the agent warms, the human closes.** Goal: turn 100 leads into about 15 ready-to-buy visitors so the salesperson only meets those 15.

## 2. Problem

Small and mid-size real estate companies run on phone calls, WhatsApp and Excel. They lose sales because:

- Leads from ads and portals wait hours for a reply and go to whoever answered first.
- Follow-ups are forgotten after the first or second call.
- Site visits are booked loosely and fall through (no reminders, no rescheduling).
- Owners and salespeople cannot tell serious leads from casual ones.

### Problems the agent cannot fix (must be handled honestly)

- **High prices.** The agent cannot change prices. It shows affordable and suitable options and tells stretched buyers the truth.
- **Builder fraud and distrust.** A company without clear RERA registration and clean documents must not be promoted by this system.

## 3. Goals and non-goals

### Goals

- Never lose a lead through slowness or forgetfulness.
- Respond in seconds, 24/7, in English, Hindi and Odia (more languages later).
- Quote only verified prices and availability.
- Hand off to humans with a full summary so the salesperson never starts from zero.
- Serve many companies from one codebase with strict data isolation.
- Meet Indian data protection and real estate rules from day one.

### Non-goals

- Negotiating price, discounts or final closing (human job).
- Giving legal or investment advice, or guaranteeing returns.
- Accepting or asking for payments outside the RERA escrow route or a licensed gateway.
- Building features nobody has asked for yet.
- Serving as a no-code tool. The product is built in code.

## 4. Users

| User | Needs |
| --- | --- |
| Buyer / renter | Fast answers, suitable options for budget, easy visit booking, honest information |
| Property owner / landlord | Easy listing intake, availability sync, tenant screening, rent tracking |
| Salesperson | Hot leads first, full summary at handoff, daily call list, draft replies |
| Company admin / owner | Visibility into leads, response time, conversion, source quality; inventory upload |
| Platform operator (us) | Tenant onboarding, monitoring, billing, security and compliance controls |

## 5. Scope by capability

### 5.1 Buyers and renters

| Capability | Requirement |
| --- | --- |
| Instant lead response | Reply within seconds on WhatsApp, website chat, Instagram, Facebook, Google lead forms and portals. Ask budget, location, BHK, purpose, timeline. |
| Lead scoring | Score by budget fit, urgency, financing readiness, engagement. Reactivate cold leads from old databases. |
| Property matching | Match needs to live inventory. Send photos, floor plans, prices, brochures. Suggest alternatives when the first choice is gone. |
| Site visit booking | Propose slots, book in team calendar, send reminders with location, handle reschedules, follow up after the visit. |
| Follow-up and nurture | Timed WhatsApp, SMS and email. Stop when the lead books or opts out. |
| Voice calling | Call new leads within minutes in Hindi, Odia, English and others. Verify interest, answer common questions, book visits. |
| Affordability check | Take income, EMIs, down payment. Show realistic budget, EMI and loan eligibility. |
| Documentation | Collect KYC, generate booking forms and payment schedules, track payment, loan and registration status. |

### 5.2 Owners and landlords (rentals)

- Listing intake (details, photos, rent and deposit expectations)
- Availability sync and visit slot confirmation
- Tenant screening with a short owner-facing summary
- Agreement drafts (drafts only), police verification tracking where required, traceable deposit and rent collection, move-in checklist
- Rent collection reminders, receipts, renewal alerts, maintenance requests
- Vacancy re-letting when a tenant gives notice

### 5.3 Company and sales team

- Human handoff with summary (budget, preferences, objections, what was shared)
- Sales copilot: pre-call briefing, suggested replies, drafted follow-ups, today's call list
- Marketing content: listing descriptions, social posts, ad copy, broadcasts, video scripts (human review of templates)
- Analytics: lead source, response time, visit-to-booking ratio, salesperson performance, where deals leak

## 6. Price and trust requirements

### Affordability

- In-chat EMI and affordability calculator
- Fit-to-budget matching (smaller units, resale, ready-to-move, plots, farther locations)
- Payment plan options in the buyer's language (subsidy schemes such as PMAY where eligible, construction-linked plans, bank tie-ups)
- Rent vs buy comparison over 5 to 10 years
- Rentals and resale as fallback revenue when new units are too expensive

### Trust and fraud protection

- Share RERA number and state RERA portal link (Odisha has its own)
- Share land title, approvals, builder track record, construction progress
- Dated construction photos and progress reports
- Verified reviews only
- Payments only into the RERA escrow account, with a clear warning against cash or personal-account payments
- Prefer ready-to-move or near-completion projects for cautious buyers
- Offer a lawyer review of the agreement before booking
- Rentals: verified listings, clear upfront costs, traceable deposits, owner document checks

### Persuasion within limits

- Real social proof only
- Approved answers to common objections
- A clear next step in every conversation
- Honest urgency only. Never fake pressure.

## 7. Handoff requirements

The agent hands off to a human when:

- The buyer asks about discount, negotiation or final price
- The buyer says "I'm interested" or asks to visit
- The buyer shows hesitation or compares with a competitor
- The lead score crosses a threshold
- Any legal question or complaint

Handoff rules are to be finalised with each client's sales team.

## 8. Non-functional requirements

- **Correctness:** prices and availability only from tool results. Wrong numbers are blocked.
- **Reliability:** if the AI is down, send a fallback message and alert a human. A lead is never left silent.
- **Idempotency:** retries never create duplicate replies, visits, reminders or payments.
- **Security and privacy:** tenant isolation via row-level security, MFA, encryption, audit logs, Indian data residency. See `rules.md`.
- **Cost:** model routing, cached answers for common questions, short context, one small server for the pilot.
- **Languages:** English, Hindi, Odia at launch.
- **Transparency:** the agent says it is an AI when asked. Voice calls say so at the start.

## 9. Success metrics

Measure what the agent controls, not whether it "sold".

| Metric | Why it matters |
| --- | --- |
| Response time | Speed advantage over the old process |
| Lead-to-visit rate | How well leads are warmed |
| Visit-to-booking rate | Lead quality reaching the salesperson |
| Follow-up completion rate | Leads no longer forgotten |
| Cost per qualified lead | Which source is worth the ad spend |

## 10. Release phases

| Phase | What ships | Rough time (solo) |
| --- | --- | --- |
| 1 | WhatsApp webhook; agent with search, qualify, save lead, handoff; basic dashboard | 3 to 4 weeks |
| 2 | Visit booking, calendar, reminders, follow-up engine, Excel import | 2 to 3 weeks |
| 3 | Rental flow: owner listings, tenant screening, agreement drafts, rent reminders | 3 to 4 weeks |
| 4 | Voice calling, analytics, multi-tenant onboarding, billing | 4 to 6 weeks |

Phase 1 or 2 is already enough to earn money. Timings are estimates.

## 11. Business model

- Setup fee plus monthly fee from day one
- Optional performance component (per visit booked or deal closed)
- Short paid pilot of one or two months with agreed metrics
- Target mid-size and large developers and brokerages with big ad spend
- Keep own costs low so one setup serves many clients

## 12. Go-to-market

1. Find one company with real lead volume.
2. Build Phase 1 and run a paid pilot for one to two months.
3. Record before and after numbers.
4. Use the numbers to pitch the next ten companies.
5. Add follow-ups, rentals and owner handling after the first piece works.
6. Move to monthly plans, then multi-tenant onboarding.

## 13. Risks

| Risk | Mitigation |
| --- | --- |
| Agent quotes a wrong price | Prices only from inventory data, output checks, audit logs |
| Slow sales cycle with owners | Paid pilots, show numbers |
| WhatsApp rules and costs | Opt-ins, templates, no spam, check current fees |
| Builder fraud affects our name | Only promote projects with clear RERA registration |
| Weak market, high prices | Rentals, resale, loan help |
| Data breach or legal penalty | Encryption, RLS, MFA, DPA, incident plan, lawyer review |
| Prompt injection or data leak via AI | Fixed tool list, tenant ID set by code, output checks, red-team tests |
| Duplicates from retries | Idempotency keys with DB unique constraints |
| Over-building early | Phased plan, features only on client demand |

## 14. Open questions

- Which pilot client, and a sample of their real listings and lead sheets?
- WhatsApp access: direct Cloud API or a provider (Gupshup, Interakt)?
- Backend choice: FastAPI or NestJS? (Spec assumes FastAPI.)
- Cloud provider and Indian region?
- Final handoff rules with the client's sales team?
- Lawyer review of consent, DPA, rental and RERA flows (Odisha-specific)
