# Frontend Coding Patterns & Style Guide

These rules govern the development of the Next.js React Dashboard for the AI Builder Cup project.

## 1. Technology Stack & Framework
- **Framework:** Next.js (App Router preferred for modern server/client component separation).
- **Language:** TypeScript. Strict typing is mandatory for all component props and state.
- **Styling:** **Vanilla CSS / CSS Modules**, one module per component. Design tokens live in `src/app/globals.css`. Do not use TailwindCSS or Bootstrap unless explicitly approved by the user.

## 2. Design System

The subject is a store shelf seen from the ceiling camera. Colors and type come from that setting, not from generic dashboard styling.

### Color tokens (`src/app/globals.css`)

| Token | Light | Dark | Use |
| :--- | :--- | :--- | :--- |
| `--shelf` | `#FAFBFB` | `#161A20` | Page background |
| `--panel` | `#F0F2F3` | `#1D232A` | Copilot panel, inset surfaces |
| `--floor` | `#D9DCDF` | `#252B33` | Map surround, thumbnail placeholders |
| `--ink` / `--ink-2` / `--ink-3` | `#1C2330` / `#47505E` / `#626B78` | `#E8EBEE` / `#B4BCC6` / `#8E98A4` | Text, from primary to muted |
| `--tag` | `#F2C230` | `#F2C230` | Price-label yellow. **Only** for things a manager should act on, the active filter, and the brand aisle (the I in the wordmark and the favicon strip). |
| `--taken` | `#2F855A` | `#5FBF8A` | Item taken |
| `--putback` | `#C8414F` | `#EF6B78` | Item put back |
| `--nopickup` | `#8F99A4` | `#6F7984` | No item picked up |

Both themes follow `prefers-color-scheme`. Add new colors as tokens in both themes, never as literals in components.

### Brand
- The mark is the aisle seen from above: two shelf bars with a yellow aisle strip between them. The strip is also the "I" in AIsle.
- Geometry, on a 16-unit grid so the 16 px favicon lands on whole pixels: ink `#1C2330` square with `rx` 3.5; shelf bars at x 3 and x 10, 3 wide; aisle at x 7, 2 wide; all from y 3, 10 high. Bars are light `--floor`, the aisle is `--tag`. The icon is the same in both themes.
- Files: `src/app/icon.svg`, `src/app/favicon.ico` (16 and 32 px), `src/app/apple-icon.tsx`, `src/app/opengraph-image.tsx`. Keep their geometry in step.
- In the UI, the brand is the `Wordmark` component: text with the I drawn as a yellow bar, sized to the I of Sofia Sans. Screen readers get "AIsle". There is no separate icon in the header.
- The Open Graph image uses static Sofia Sans files in `src/app/_brand/`, because its renderer takes no variable fonts.

### Type
- One superfamily, loaded with `next/font/google`: **Sofia Sans** for text (`--font-text`) and **Sofia Sans Extra Condensed** for figures (`--font-figure`). Both are variable in weight.
- Figures use the `.figure` class: the extra-condensed cut, heavy weight and tabular numerals, like the price on a shelf tag. Headings use weight 700; Sofia Sans reads lighter than its number suggests.
- Sentence case everywhere. No all-caps labels, no monospace labels, no emojis in the UI.

### Words
- Use the store's terms: "taken", "put back", "no pick-up", "time at shelf". Not "conversion", "cart abandonment" or "dwell".
- Count what the data counts: a record is a **clip**, not a visit or a shopper.
- Show only measured numbers. Do not display placeholder or hardcoded telemetry.
- Errors say what failed and what to do next. They do not apologize.
- Cut copy the layout already shows. No captions that restate a chart, no labels above self-evident controls, no subtitles that describe the panel.
- Gemini text is kept short at the source: findings carry a title and an `action` of 15 words or fewer. Long summaries are clamped in lists and shown in full in the replay.

### Numbers
- Counts first, percentages second. Write "5 put back" large and "36% of picked up" small.
- Every percentage states its base. Use one base per view.
- The shelf funnel is the main metric: stopped, then picked up or no pick-up, then taken or put back. Band size is proportional to the count. It follows the selected zone, and its bands filter the clip list.

### Motion
- Only in response to a user action: opening a clip, choosing a zone, hover on a control.
- Respect `prefers-reduced-motion` (handled globally in `globals.css`).

### Layout
- Order: shelf funnel, then the overhead shelf map with findings, then the clip list. Every number links to the clips behind it.
- Copilot is an always-visible side panel on wide screens and a bottom sheet under 960px.
- Must work at 390px width without horizontal scrolling.

## 3. Component Architecture
- Keep components small and focused.
- Separate data-fetching logic from presentational components. Server data goes through TanStack Query hooks in `src/lib/queries.ts`; components do not call `fetch` directly.
- Use Server Components by default; only use `use client` when interactivity (e.g., hooks, state, event listeners) is required.

## 4. API & Data Handling
- API types are generated from the backend's OpenAPI schema into `src/lib/api.gen.ts` with `npm run gen:api`. Do not write them by hand; re-export them from `src/lib/api.ts`.
- Handle loading states gracefully: show a clear loading state, never placeholder zeros.
- Provide clear error boundaries and user-friendly error messages if the Gen AI chat fails to respond.

## 5. SEO & Accessibility
- **Semantic HTML:** Use proper tags (`<header>`, `<main>`, `<section>`, `<article>`).
- **Headings:** One `<h1>` per page.
- **Accessible names:** Every interactive element has a role and an accessible name (visible text or `aria-label`). Browser tests select elements by role and name, as Playwright and Testing Library recommend, not by IDs added for testing.
