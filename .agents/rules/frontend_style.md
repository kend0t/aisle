# Frontend Coding Patterns & Style Guide

These rules govern the development of the Next.js React Dashboard for the AI Builder Cup project.

## 1. Technology Stack & Framework
- **Framework:** Next.js (App Router preferred for modern server/client component separation).
- **Language:** TypeScript. Strict typing is mandatory for all component props and state.
- **Styling:** **Vanilla CSS / CSS Modules**. Per system guidelines, prioritize raw CSS to achieve highly customized, premium aesthetics (glassmorphism, subtle micro-animations, tailored HSL color palettes). Do not use TailwindCSS or Bootstrap unless explicitly approved by the user.

## 2. Design Aesthetics & UX (CRITICAL FOR HACKATHON)
- **Premium Feel:** The dashboard must not look like a generic template. It should have a "WOW" factor.
- **Animations:** Implement subtle CSS transitions for all interactive elements (hover states, chart loading, modal popups).
- **Data Visualization:** Charts and metrics should be clean, using harmonious color palettes rather than default primary colors.

## 3. Component Architecture
- Keep components small and focused.
- Separate data-fetching logic from presentational components. 
- Use Server Components by default; only use `use client` when interactivity (e.g., hooks, state, event listeners) is required.

## 4. API & Data Handling
- All data models coming from Firestore must have corresponding TypeScript interfaces.
- Handle loading states gracefully (e.g., use skeleton loaders instead of blank screens while fetching analytics).
- Provide clear error boundaries and user-friendly error messages if the Gen AI chat fails to respond.

## 5. SEO & Accessibility
- **Semantic HTML:** Use proper tags (`<header>`, `<main>`, `<section>`, `<article>`).
- **Headings:** One `<h1>` per page.
- **Unique IDs:** Ensure all interactive elements have unique, descriptive IDs for browser testing and accessibility.
