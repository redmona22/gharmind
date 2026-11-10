# Design Spec: Gharmind Admin Dashboard

Source: Real_Estate_AI_Agent_Build_Plan.docx, sections 2.3 and 9. Palette: charcoal + orange (bold, energetic). Stack: React with Tailwind.

## 1. Design principles

- **Speed to action.** A salesperson opens the dashboard to find the hottest lead and act. Hot leads first, always.
- **Trust through clarity.** Show source of every number. Prices and RERA numbers are never hidden.
- **Human takeover is one click.** Reading a chat and taking over must be effortless.
- **Version one is three views.** Leads and conversations, Listings, Visits and reports. Nothing else yet.
- **Mobile-friendly.** Salespeople work from phones between site visits.
- **Per-company branding later.** Use design tokens so a tenant's logo and accent can be swapped.

## 2. Color palette

| Token | Hex | Use |
| --- | --- | --- |
| `--charcoal-950` | `#14161A` | App background (dark sidebar, top bar) |
| `--charcoal-900` | `#1C1F24` | Cards on dark surfaces |
| `--charcoal-800` | `#262A31` | Raised surfaces, hover |
| `--charcoal-600` | `#4A505A` | Borders, secondary icons |
| `--charcoal-400` | `#8A919C` | Secondary text |
| `--charcoal-200` | `#D5D8DD` | Borders on light surfaces |
| `--charcoal-50` | `#F5F6F8` | Page background (light content area) |
| `--white` | `#FFFFFF` | Cards, primary text on dark |
| `--orange-500` | `#F97316` | Primary accent: buttons, active nav, key highlights |
| `--orange-600` | `#EA580C` | Primary hover / pressed |
| `--orange-100` | `#FFEDD5` | Subtle highlight backgrounds, selected rows |

### Status colors

| Meaning | Hex | Use |
| --- | --- | --- |
| Hot lead / success | `#16A34A` | Booked, done, resolved |
| Warning | `#F59E0B` | Pending, nearing threshold |
| Danger | `#DC2626` | Opted out, failed send, no-show, blocked reply |
| Info | `#2563EB` | Neutral notices |

### Rules

- Orange is the single accent. Use it for the one primary action per screen, active navigation and key metrics.
- Orange text on white fails contrast at small sizes. Use `#C2410C` for orange text on light backgrounds; use `#F97316` on charcoal.
- Never rely on color alone. Pair status colors with an icon or label.
- Body text on light: `#14161A`. On dark: `#FFFFFF` or `#D5D8DD`.
- Minimum contrast: 4.5:1 for body text, 3:1 for large text and UI components.

## 3. Typography

- Font: Inter (fallback: system-ui, sans-serif). Supports Latin and Devanagari via fallback; add Noto Sans Devanagari and Noto Sans Oriya so Hindi and Odia messages render correctly in chat views.
- Scale: 12 / 14 / 16 / 20 / 24 / 32 px. Body 14 or 16.
- Weights: 400 body, 500 labels, 600 headings.
- Numbers (prices, scores): tabular figures.

## 4. Spacing, shape, elevation

- 4 px base grid (Tailwind default scale).
- Cards: 8 px radius, 1 px border `--charcoal-200`, minimal shadow.
- Buttons and inputs: 6 px radius, 40 px height (44 px on mobile touch targets).
- Dark chrome (sidebar, top bar) with a light content area keeps data readable.

## 5. Layout

- **Desktop:** fixed dark sidebar (240 px) with three nav items; top bar with search, tenant name and user menu; content area on `--charcoal-50`.
- **Mobile:** bottom tab bar with the three views; chat and lead detail open full-screen.
- Max content width 1280 px.

## 6. Components

- **Button:** primary (orange fill, white text), secondary (charcoal outline), ghost, destructive (red).
- **Lead card / row:** name, phone (masked for roles that should not see it), score badge, source, last activity, assigned salesperson, status chip.
- **Score badge:** Hot (green), Warm (amber), Cold (grey). Show number and label.
- **Status chips:** conversation (agent handling, human handling, handoff open, opted out), visit (booked, done, no-show), listing (available, held, sold or rented, not promotable).
- **Chat bubbles:** client (white, left), agent (orange-100, right, labelled "AI"), human (charcoal, right, labelled with name). Tool calls shown as small collapsible notes.
- **Handoff banner:** orange-bordered card with summary: budget, preferences, objections, what was shared.
- **Data table:** sortable, filterable, sticky header, row selection, empty and loading states.
- **Calendar:** week and day views for visits, color by status.
- **Metric card:** big number, label, trend delta.
- **Toasts and inline errors:** clear text, never silent failures.
- **Consent badge:** shows opt-in status and time on the contact.

## 7. Views (version one)

### 7.1 Leads and conversations

- Left: lead list, sorted by score by default; filters for source, score, status, assigned person, type (sale or rent).
- Center: conversation thread with composer.
- Right: contact profile, qualification answers, score reasons, shared listings, handoff summary, consent status.
- Primary action: **Take over** (switches to human; agent stops replying). Secondary: **Hand back to agent**.
- Opted-out contacts show a locked composer with a clear reason.

### 7.2 Listings

- Table and card toggle. Columns: type, project, price or rent, deposit, BHK, area, furnishing, status, RERA number.
- Sale listings without a RERA number show a red "Not promotable" chip and cannot be set live.
- Excel import with column mapping, preview, error report.
- Media upload with drag and drop.

### 7.3 Visits and reports

- Calendar of visits with status colors; click for contact and listing.
- Metrics: response time, lead-to-visit rate, visit-to-booking rate, follow-up completion rate, cost per qualified lead by source.
- Date range filter and per-salesperson breakdown.
- Export to CSV.

## 8. Roles and visibility

| Role | Sees |
| --- | --- |
| Salesperson | Own leads and conversations; listings read-only; own visits |
| Admin | Everything in own company; manage users and listings |
| Owner (later portal) | Own properties, tenant summaries, rent tracking |
| Platform operator | Tenant settings only; no routine access to chat content |

Sensitive fields (income, ID numbers) are masked by default and reveal is logged in the audit log.

## 9. Security and privacy in the UI

- MFA setup and login flow.
- Session timeout and re-auth for sensitive reveals or exports.
- Every export and sensitive view writes an audit entry.
- Privacy tools per contact: view stored data, correct, export, delete request with due date.
- No raw PII in error screens or analytics.

## 10. Accessibility and language

- WCAG AA contrast, visible focus states (orange outline), full keyboard navigation.
- Labels on all inputs, aria labels on icon buttons.
- UI in English first. Message content must render Hindi and Odia correctly.
- Respect reduced-motion settings.

## 11. Later additions

Owner portal, tenant and rent tracking, billing, per-company branding (logo, accent color override via tokens).

## 12. Tailwind tokens (starting point)

```js
// tailwind.config.js
theme: {
  extend: {
    colors: {
      charcoal: {
        50: '#F5F6F8', 200: '#D5D8DD', 400: '#8A919C',
        600: '#4A505A', 800: '#262A31', 900: '#1C1F24', 950: '#14161A',
      },
      brand: { 100: '#FFEDD5', 500: '#F97316', 600: '#EA580C', text: '#C2410C' },
      success: '#16A34A', warning: '#F59E0B', danger: '#DC2626', info: '#2563EB',
    },
    fontFamily: {
      sans: ['Inter', 'Noto Sans Devanagari', 'Noto Sans Oriya', 'system-ui', 'sans-serif'],
    },
  },
}
```
