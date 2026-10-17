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
| `--tag` | `#F2C230` | `#F2C230` | Price-label yellow. **Only** for things a manager should act on, and the active filter. |
| `--taken` | `#2F855A` | `#5FBF8A` | Item taken |
| `--putback` | `#C8414F` | `#EF6B78` | Item put back |
| `--nopickup` | `#8F99A4` | `#6F7984` | No item picked up |

Both themes follow `prefers-color-scheme`. Add new colors as tokens in both themes, never as literals in components.

### Type
- One family: **Archivo** (variable, loaded with `next/font/google`).
- Figures use the `.figure` class: condensed width (`wdth` 72) and tabular numerals, like the price on a shelf label.
- Sentence case everywhere. No all-caps labels, no monospace labels, no emojis in the UI.

### Words
- Use the store's terms: "taken", "put back", "no pick-up", "time at shelf". Not "conversion", "cart abandonment" or "dwell".
- Count what the data counts: a record is a **clip**, not a visit or a shopper.
- Show only measured numbers. Do not display placeholder or hardcoded telemetry.
- Errors say what failed and what to do next. They do not apologize.

### Motion
- Only in response to a user action: opening a clip, choosing a zone, hover on a control.
- Respect `prefers-reduced-motion` (handled globally in `globals.css`).

### Layout
- The overhead shelf map is the hero. Every number links to the clips behind it.
- Copilot is an always-visible side panel on wide screens and a bottom sheet under 960px.
- Must work at 390px width without horizontal scrolling.

## 3. Component Architecture
- Keep components small and focused.
- Separate data-fetching logic from presentational components. 
- Use Server Components by default; only use `use client` when interactivity (e.g., hooks, state, event listeners) is required.

## 4. API & Data Handling
- All data models coming from Firestore must have corresponding TypeScript interfaces.
- Handle loading states gracefully: show a clear loading state, never placeholder zeros.
- Provide clear error boundaries and user-friendly error messages if the Gen AI chat fails to respond.

## 5. SEO & Accessibility
- **Semantic HTML:** Use proper tags (`<header>`, `<main>`, `<section>`, `<article>`).
- **Headings:** One `<h1>` per page.
- **Unique IDs:** Ensure all interactive elements have unique, descriptive IDs for browser testing and accessibility.
