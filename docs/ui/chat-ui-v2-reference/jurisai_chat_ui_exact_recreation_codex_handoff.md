# JurisAI Main Chat UI — Exact Recreation Handoff for Codex

## Purpose

This document is a strict implementation brief for recreating the JurisAI chat UI concept as closely as possible from the generated UX mockups.

The previous implementation attempt looked good but became visually toned down. The goal here is not to create a generic dark chatbot. The goal is to recreate the premium, polished, dark, blue-accented, Behance-style JurisAI interface with the same hierarchy, density, glow, spacing, background atmosphere, sidebar, chat surface, scheme shortlist, landing narrative, and live background-step animation system.

The implementation should prioritize visual fidelity over minimal code. Do not simplify the UI unless explicitly instructed.

---

# 1. Product Narrative

## Core positioning

JurisAI helps citizens discover government schemes that match their real situation.

Most people know only a few popular schemes. Many useful schemes remain hidden because users do not know the exact scheme name, eligibility language, ministry name, or category to search for.

The main landing/chat screen should communicate:

> “You do not need to know the scheme name. Tell JurisAI your situation, and it will help uncover relevant schemes.”

## Primary UX promise

1. Make government schemes more discoverable.
2. Make scheme exploration feel guided, not overwhelming.
3. Show background progress in human language.
4. Ground answers in official sources and retrieved scheme context.
5. Allow both guided discovery and full browsing.

## Required landing-page copy direction

Use this general tone:

- Calm
- Trustworthy
- Premium
- Government/legal clarity
- Not playful
- Not corporate SaaS cliché
- Not overly bureaucratic

Suggested hero copy:

```text
Welcome to JurisAI
Discover schemes that match your needs — not just the popular ones.
```

Supporting message:

```text
Tell us about your situation and we’ll help uncover schemes you may not know about.
```

Or:

```text
Most people know only the popular schemes. JurisAI helps surface lesser-known programs that may actually fit your situation.
```

---

# 2. Visual Direction

## Overall feel

The UI should feel like:

- ChatGPT-style interaction clarity
- Perplexity-style source transparency
- Linear-style dark polish
- Government/legal trust language
- Premium portfolio-grade dark interface

It must not feel like:

- Bootstrap dashboard
- Plain Tailwind dark mode
- Generic chatbot
- Flat black rectangle layout
- Overly bright neon cyberpunk
- Simplified mobile-first MVP

## Design keywords

- Deep navy-black
- Glass panels
- Soft electric-blue highlights
- Thin borders
- Rounded corners
- Subtle inner glow
- Soft drop shadows
- Elegant serif display headings in presentation surfaces
- Clean sans-serif UI text
- Compact but readable density
- Calm animated states

---

# 3. Color System

Use CSS variables. Do not use random hardcoded grays throughout the app.

```css
:root {
  --bg-page: #05080d;
  --bg-page-2: #070b12;
  --bg-shell: #080d15;
  --bg-panel: rgba(13, 19, 30, 0.88);
  --bg-panel-solid: #0d131e;
  --bg-panel-raised: rgba(18, 26, 39, 0.92);
  --bg-panel-soft: rgba(255, 255, 255, 0.035);

  --surface-1: #0a0f16;
  --surface-2: #111822;
  --surface-3: #171e2a;
  --surface-4: #1e2635;

  --border-subtle: rgba(148, 163, 184, 0.12);
  --border-default: rgba(148, 163, 184, 0.18);
  --border-strong: rgba(96, 165, 250, 0.38);

  --text-primary: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-muted: #94a3b8;
  --text-dim: #64748b;

  --blue-300: #93c5fd;
  --blue-400: #60a5fa;
  --blue-500: #3b82f6;
  --blue-600: #2563eb;
  --blue-glow: rgba(59, 130, 246, 0.45);

  --success: #22c55e;
  --success-soft: rgba(34, 197, 94, 0.14);
  --warning: #f59e0b;
  --warning-soft: rgba(245, 158, 11, 0.14);
  --danger: #ef4444;

  --shadow-soft: 0 18px 80px rgba(0, 0, 0, 0.35);
  --shadow-blue: 0 0 0 1px rgba(96, 165, 250, 0.28), 0 0 48px rgba(37, 99, 235, 0.16);
}
```

## Background treatment

The page must not be flat black.

Use layered radial gradients:

```css
body {
  background:
    radial-gradient(circle at 18% 8%, rgba(37, 99, 235, 0.18), transparent 34%),
    radial-gradient(circle at 82% 18%, rgba(59, 130, 246, 0.12), transparent 30%),
    radial-gradient(circle at 50% 90%, rgba(15, 23, 42, 0.9), transparent 45%),
    linear-gradient(180deg, #05080d 0%, #070b12 48%, #05080d 100%);
}
```

Add a subtle noise overlay if possible:

```css
.app-root::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.035;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.45'/%3E%3C/svg%3E");
}
```

---

# 4. Typography

## Fonts

Use a refined sans-serif for UI and optionally a serif display font for big landing titles.

Recommended:

```css
--font-ui: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-display: "Playfair Display", Georgia, serif;
```

If external fonts are unavailable, use system stack but preserve sizing and weight.

## Type scale

```css
--text-xs: 11px;
--text-sm: 12px;
--text-md: 14px;
--text-base: 15px;
--text-lg: 18px;
--text-xl: 22px;
--display-sm: 32px;
--display-md: 44px;
--display-lg: 58px;
```

## UI text rules

- Message body: 15px to 16px, line-height 1.65
- Metadata: 11px to 12px, uppercase when useful
- Scheme cards: 13px to 14px
- Buttons/chips: 12px to 13px
- Hero title: 32px to 46px inside app landing state

---

# 5. Overall Layout

## Desktop structure

The main screen has:

```text
┌────────────────────────────────────────────────────────────┐
│ App shell                                                   │
│ ┌─────────────┬──────────────────────────┬────────────────┐ │
│ │ Sidebar     │ Main Chat / Landing      │ Scheme Panel   │ │
│ │             │                          │                │ │
│ │             │ Composer                 │                │ │
│ └─────────────┴──────────────────────────┴────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

Recommended grid:

```css
.chat-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) clamp(320px, 28vw, 390px);
  min-height: calc(100vh - 48px);
}
```

If there is no right panel yet, keep the visual width but show the landing suggestion/matches panel.

## Main app container

```css
.chat-shell {
  max-width: 1440px;
  margin: 24px auto;
  border: 1px solid var(--border-default);
  border-radius: 24px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(8, 13, 21, 0.94));
  box-shadow: var(--shadow-soft), var(--shadow-blue);
  backdrop-filter: blur(22px);
}
```

---

# 6. Sidebar Specification

## Sidebar purpose

The sidebar reinforces product structure and trust. It should feel useful but not dominate.

Required nav items:

- Chat — active
- Schemes
- Saved
- History
- Notifications with count badge
- Settings

Bottom section:

- Citizen Mode / General Guidance
- Small legal disclaimer card

## Sidebar styling

```css
.sidebar {
  background: rgba(5, 10, 18, 0.72);
  border-right: 1px solid var(--border-subtle);
  padding: 20px 14px;
}
```

Active nav item:

```css
.nav-item.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.85), rgba(30, 64, 175, 0.62));
  color: white;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.14), 0 10px 28px rgba(37,99,235,0.18);
}
```

Regular nav:

```css
.nav-item {
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  padding: 0 12px;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(255,255,255,0.045);
}
```

---

# 7. Topbar Specification

Topbar sits above the conversation and scheme panel, not above the whole browser page.

Required elements:

- Brand mini icon + JurisAI
- Conversation status chip
- Optional conversation title/dropdown
- Sources button
- New chat button
- Help
- Theme icon
- User avatar

## Topbar style

```css
.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(9, 14, 23, 0.62);
  backdrop-filter: blur(18px);
}
```

Status chip:

```css
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 11px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.1);
  color: #bbf7d0;
  border: 1px solid rgba(34, 197, 94, 0.22);
  font-size: 12px;
}
```

---

# 8. Landing / Empty State

## Main landing state

This is essential. The landing screen must not be a blank chat.

Central block:

```text
Welcome to JurisAI
Discover schemes that match your needs — not just the popular ones.
```

Three explanatory mini cards:

1. Tell us your situation
   - Share what you need, your location and profile.
2. We uncover matches
   - We search across thousands of government schemes.
3. Clear, guided answers
   - Understand eligibility, benefits and how to apply.

## Starter prompt cards

Required examples:

```text
I am a woman entrepreneur in Maharashtra
Find scholarships I may be eligible for
Show schemes for medical support
What schemes can help rural families?
```

Each card should have:

- Dark elevated surface
- 1px subtle border
- Slight hover glow
- Arrow icon at bottom/right
- 14px text

## Explore all schemes CTA

This is a required part of the narrative.

Place below starter cards:

```text
Explore all schemes
Browse by category, ministry and your state.
```

This can navigate to `/schemes` or a placeholder until implemented.

Style it like a wide premium card, not a plain button.

```css
.explore-all-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: 18px;
  padding: 18px 20px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(8, 13, 21, 0.9));
  border: 1px solid var(--border-default);
}
```

---

# 9. Composer Specification

The composer must look premium and slightly glowing.

## Required controls

- Main textarea/input
- Attach button
- Microphone button
- Send button
- Optional context chips: State, Beneficiary, Mode
- Shift + Enter hint

## Composer style

```css
.composer {
  border-radius: 22px;
  border: 1px solid rgba(96, 165, 250, 0.56);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.85), rgba(8, 13, 21, 0.95));
  box-shadow:
    0 0 0 1px rgba(37, 99, 235, 0.16),
    0 0 38px rgba(37, 99, 235, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  padding: 14px;
}
```

Send button:

```css
.send-button {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--blue-500), var(--blue-600));
  box-shadow: 0 10px 30px rgba(37,99,235,0.35);
}
```

---

# 10. Chat Message Specification

## User bubble

- Right aligned
- Blue gradient
- Rounded 18px
- Width max 66ch
- Timestamp above or inline

```css
.message.user .bubble {
  background: linear-gradient(135deg, #2f63d8, #1d4ed8);
  color: white;
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 12px 32px rgba(37, 99, 235, 0.26);
}
```

## Assistant bubble

- Left aligned
- Dark elevated card
- Max width 78ch
- Good Markdown typography
- Sources and suggestion chips below

```css
.message.assistant .bubble {
  background: linear-gradient(180deg, rgba(18, 26, 39, 0.95), rgba(11, 17, 27, 0.96));
  border: 1px solid var(--border-subtle);
  border-radius: 20px 20px 20px 6px;
  box-shadow: 0 16px 50px rgba(0,0,0,0.24);
}
```

---

# 11. Scheme Shortlist Panel

## Purpose

The right panel supports discovery. It should not visually overpower the chat.

Required title variants:

- Suggested matches
- Scheme Shortlist
- Top matches for you

## Panel contents

Each scheme card should include:

- Rank number
- Scheme title
- Match label: High Match / Medium Match / Low Match
- One-line summary
- Tags: Loan, Central, Women, Maharashtra, Skill, Scholarship, etc.
- Bookmark or chevron icon

Required CTA:

```text
View all schemes
```

Required browse-everything card:

```text
Prefer to browse everything?
Explore the complete scheme catalog across ministries and states.
```

## Card styling

```css
.scheme-card {
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(8, 13, 21, 0.92));
  padding: 14px;
}

.scheme-card:hover {
  border-color: rgba(96, 165, 250, 0.32);
  transform: translateY(-1px);
  box-shadow: 0 14px 42px rgba(0,0,0,0.28);
}
```

Match pills:

```css
.match.high {
  color: #bbf7d0;
  background: rgba(34,197,94,0.14);
  border: 1px solid rgba(34,197,94,0.24);
}

.match.medium {
  color: #bfdbfe;
  background: rgba(59,130,246,0.14);
  border: 1px solid rgba(59,130,246,0.24);
}

.match.low {
  color: #fde68a;
  background: rgba(245,158,11,0.14);
  border: 1px solid rgba(245,158,11,0.24);
}
```

---

# 12. Background Steps / Animation System

This is the key feature from the latest generated image.

## Existing backend states

If the code already has stored stage entries, map those technical backend states to user-readable steps. Never expose raw technical names by default.

Example mapping:

```ts
const FRIENDLY_STEPS = [
  {
    key: 'understanding_intent',
    label: 'Understanding user intent',
    description: 'Reading your question and identifying what kind of help you need.',
  },
  {
    key: 'extracting_context',
    label: 'Extracting location and profile context',
    description: 'Looking for location, beneficiary type, category, purpose, and constraints.',
  },
  {
    key: 'retrieving_schemes',
    label: 'Retrieving relevant schemes',
    description: 'Searching across available government scheme records.',
  },
  {
    key: 'ranking_matches',
    label: 'Ranking possible matches',
    description: 'Prioritizing schemes that best match the user’s situation.',
  },
  {
    key: 'checking_eligibility',
    label: 'Checking eligibility signals',
    description: 'Comparing scheme criteria against the information provided.',
  },
  {
    key: 'grounding_sources',
    label: 'Grounding with official sources',
    description: 'Preparing references and source-backed context.',
  },
  {
    key: 'drafting_answer',
    label: 'Drafting the answer',
    description: 'Writing a clear, guided response.',
  },
]
```

## Step status model

Each step has one of:

```ts
type StepStatus = 'pending' | 'active' | 'complete' | 'error'
```

## Visual step panel

Title:

```text
How JurisAI is helping
```

Optional alternative:

```text
Discovery in progress
```

Panel structure:

```text
How JurisAI is helping        Hide steps ^

1  Understanding user intent                 Complete ✓
2  Extracting location and profile context   Complete ✓
3  Retrieving relevant schemes               In progress ○
4  Ranking possible matches                  Pending
5  Checking eligibility signals              Pending
6  Grounding with official sources           Pending
7  Drafting the answer                       Pending
```

Panel style:

```css
.steps-panel {
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.34);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.90), rgba(8, 13, 21, 0.96));
  box-shadow:
    0 0 0 1px rgba(37, 99, 235, 0.12),
    0 18px 60px rgba(0,0,0,0.32),
    0 0 42px rgba(37,99,235,0.12);
  padding: 14px;
}
```

Step row:

```css
.step-row {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 34px;
}
```

Step number:

```css
.step-number {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 11px;
  color: var(--text-secondary);
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.step-row.complete .step-number {
  background: rgba(34,197,94,0.16);
  border-color: rgba(34,197,94,0.34);
  color: #bbf7d0;
}

.step-row.active .step-number {
  background: rgba(59,130,246,0.18);
  border-color: rgba(96,165,250,0.46);
  color: #bfdbfe;
  box-shadow: 0 0 22px rgba(59,130,246,0.25);
}
```

Active spinner:

```css
.active-spinner {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid rgba(96,165,250,0.22);
  border-top-color: var(--blue-400);
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

Pulse dot:

```css
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--blue-400);
  box-shadow: 0 0 0 rgba(96,165,250,0.45);
  animation: pulse 1.6s ease-out infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(96,165,250,0.42); }
  70% { box-shadow: 0 0 0 9px rgba(96,165,250,0); }
  100% { box-shadow: 0 0 0 0 rgba(96,165,250,0); }
}
```

## Collapsed step state

When collapsed, show:

```text
JurisAI is retrieving relevant schemes…
```

Or:

```text
Working on your answer — retrieving schemes
```

With a subtle active dot.

## Animation behavior

Use Framer Motion if available.

Required motion timing:

- Step panel appears: 180–220ms ease-out
- Step row status changes: 120–180ms
- Shortlist panel update: 180–240ms
- Chips appear: 100–140ms stagger
- Assistant streaming cursor: subtle pulse every 1s

Framer example:

```tsx
<motion.div
  initial={{ opacity: 0, y: 8, scale: 0.985 }}
  animate={{ opacity: 1, y: 0, scale: 1 }}
  exit={{ opacity: 0, y: 4, scale: 0.99 }}
  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
/>
```

---

# 13. Behind-the-Scenes Mini Storyboard

The latest generated mockup shows a small horizontal storyboard called:

```text
A peek behind the scenes
```

This should be implemented either as a static explanatory element on the landing page or a hidden/expanded visualization in the step panel.

Flow:

```text
Idle -> Understanding -> Retrieving -> Shortlist ready -> Answer streaming
```

Each card should have:

- Icon
- Number
- Short label
- One-line explanation
- Connector arrow

Example:

```text
1. Idle
Waiting for your question.

2. Understanding
We understand your intent and context.

3. Retrieving
Searching across thousands of schemes.

4. Shortlist ready
Top matches prepared for your review.

5. Answer streaming
Guided answer with clear explanations.
```

Style:

```css
.storyboard-card {
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(15,23,42,0.78), rgba(8,13,21,0.92));
  border: 1px solid var(--border-default);
  min-height: 120px;
  padding: 16px;
}

.storyboard-card.active {
  border-color: rgba(96,165,250,0.48);
  box-shadow: 0 0 36px rgba(37,99,235,0.16);
}
```

---

# 14. Responsive Rules

## Desktop >= 1180px

- Three-column shell: sidebar, conversation, scheme panel.
- Scheme panel visible.
- Composer sticky/floating at bottom of conversation.

## Tablet 768px–1179px

- Sidebar compresses to icon rail or becomes collapsible.
- Scheme panel turns into a drawer.
- Show button: `Show scheme shortlist (5)`.

## Mobile <= 767px

- Chat takes full screen.
- Scheme shortlist becomes bottom sheet.
- Composer remains sticky near bottom thumb zone.
- Topbar becomes compact.
- Hide secondary labels.

Important: do not stack the full scheme panel below the chat on mobile by default. It will become too long and destroy focus.

---

# 15. Implementation Notes for Existing Code

## Likely files to modify

Based on the current project structure:

```text
web/src/routes/ChatPage.tsx
web/src/App.css
web/src/index.css
web/src/types.ts
```

Primary changes should happen in:

1. `ChatPage.tsx` for component structure and stage rendering.
2. `App.css` for visual fidelity.
3. `types.ts` only if stage/message types need refinement.

## Suggested component breakdown

Refactor if needed:

```text
ChatPage
  AppShell
    Sidebar
    ChatWorkspace
      ChatTopbar
      LandingState
      MessageList
      LiveAssistantBubble
      BackgroundStepsPanel
      Composer
    SchemeShortlistPanel
      SchemeCard
      BrowseAllSchemesCard
```

If avoiding a full refactor, still add class names that map to this structure.

## Performance requirements

- Memoize `MessageBubble`.
- Memoize `SchemeCard`.
- Keep streaming answer isolated so every token does not re-render the whole screen.
- Only auto-scroll if user is near bottom.
- Respect `prefers-reduced-motion`.

---

# 16. Exact UI Copy Library

Use this copy unless better product copy is explicitly approved.

## Landing

```text
Welcome to JurisAI
Discover schemes that match your needs — not just the popular ones.
```

```text
Tell us your situation
Share what you need, your location and profile.
```

```text
We uncover matches
We search across thousands of government schemes.
```

```text
Clear, guided answers
Understand eligibility, benefits and how to apply.
```

## Composer placeholder

```text
Ask about your situation, eligibility, education, business, health, or support...
```

## Starter cards

```text
I am a woman entrepreneur in Maharashtra
Find scholarships I may be eligible for
Show schemes for medical support
What schemes can help rural families?
```

## Browse all schemes

```text
Explore all schemes
Browse by category, ministry and your state.
```

## Right panel

```text
Suggested matches
Top schemes for you based on your context and current query.
```

```text
Prefer to browse everything?
Explore the complete scheme catalog across ministries and states.
```

## Step panel

```text
How JurisAI is helping
```

Steps:

```text
Understanding user intent
Extracting location and profile context
Retrieving relevant schemes
Ranking possible matches
Checking eligibility signals
Grounding with official sources
Drafting the answer
```

Info bar:

```text
You stay in control. You can interrupt, refine, or ask follow-up questions at any time.
```

---

# 17. Common Mistakes to Avoid

Do not:

1. Flatten all panels into plain dark gray boxes.
2. Remove glow/border layering.
3. Make the sidebar too bright.
4. Make the composer look like a plain input.
5. Hide the scheme shortlist entirely on desktop.
6. Expose raw backend stage names.
7. Use overly large text in scheme cards.
8. Use pure black background.
9. Use random blues or inconsistent border colors.
10. Remove the `Explore all schemes` browsing path.
11. Make the page only a chatbot; it must communicate discoverability.
12. Use excessive animation that distracts from reading.

---

# 18. Acceptance Criteria

The implementation is successful only if:

- The page immediately communicates “scheme discoverability,” not just “chatbot.”
- The dark visual system feels premium and layered.
- The composer has a blue glow and rich controls.
- The scheme panel is clearly visible on desktop.
- The landing screen has starter cards and `Explore all schemes`.
- Background steps appear in human-readable language while answering.
- Step statuses visually change between complete, active, and pending.
- The UI remains responsive with drawer/bottom-sheet behavior.
- The result feels close to the generated mockups, not a toned-down version.

---

# 19. Suggested First Codex Prompt

Use this prompt with Codex:

```text
You are editing the JurisAI web UI. Recreate the premium dark JurisAI chat redesign from the handoff document as closely as possible. Focus on visual fidelity, not simplification.

Modify the existing React/Vite UI, primarily ChatPage.tsx and App.css.

Requirements:
1. Build a three-column desktop layout: sidebar, main chat/landing area, right scheme shortlist panel.
2. Add a landing empty state with the narrative: “Discover schemes that match your needs — not just the popular ones.”
3. Add starter prompt cards and an “Explore all schemes” CTA.
4. Add a premium glowing composer with attach, microphone, and send controls.
5. Add a scheme shortlist panel with suggested matches, match labels, tags, and a “View all schemes” CTA.
6. Add a human-readable background steps panel that maps existing backend/stage states to friendly steps like understanding intent, extracting context, retrieving schemes, ranking matches, checking eligibility, grounding sources, and drafting answer.
7. Preserve SSE streaming behavior and existing chat functionality.
8. Use the exact CSS design tokens and visual rules from this document: deep navy background, glass panels, blue glow, subtle borders, rounded cards, premium dark interface.
9. Add responsive behavior: side shortlist on desktop, drawer/tablet behavior, bottom sheet or collapsed source access on mobile.
10. Do not tone down the design into a generic dark chat interface.

After changes, summarize files changed and key implementation decisions.
```

---

# 20. Suggested Follow-up Codex Prompt for Fidelity

Use this if Codex produces something too plain:

```text
The UI is functionally correct but visually too toned down. Increase fidelity to the mockup.

Please improve:
1. Add layered radial-gradient page background and subtle noise overlay.
2. Strengthen panel borders, inner highlights, and blue glows.
3. Make the composer visually premium with a clear blue focus/glow border.
4. Add more spacing and rounded-card polish to the landing prompt cards.
5. Make the scheme shortlist look like a premium right-side discovery panel with rank numbers, match badges, tags, and hover states.
6. Make the background steps panel look like a polished live-status module with complete/active/pending states and subtle animation.
7. Ensure the UI visually resembles the generated UX boards, not a basic dashboard.
```
