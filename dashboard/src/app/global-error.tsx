"use client";

import { useEffect } from "react";
import { errorMessage } from "@/lib/api";

// This replaces the root layout, so globals.css and the fonts are not loaded. The colors
// repeat the --shelf, --ink, --ink-2 and --line tokens for both themes.
const css = `
  :root { color-scheme: light dark; }
  body {
    margin: 0;
    background: #fafbfb;
    color: #1c2330;
    font: 16px/1.5 system-ui, sans-serif;
  }
  main { max-width: 64ch; margin: 80px auto; padding: 0 16px; display: flex; flex-direction: column; gap: 12px; }
  h1 { margin: 0; font-size: 1.75rem; line-height: 1.2; }
  p { margin: 0; color: #47505e; }
  button {
    align-self: flex-start;
    margin-top: 8px;
    padding: 6px 14px;
    border: 1px solid #d3d7db;
    border-radius: 6px;
    background: none;
    color: inherit;
    font: inherit;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #161a20; color: #e8ebee; }
    p { color: #b4bcc6; }
    button { border-color: #2f3740; }
  }
`;

/** Catches errors in the root layout itself. */
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <title>AIsle</title>
        <style>{css}</style>
        <main aria-live="polite">
          <h1>The dashboard stopped working.</h1>
          <p>{errorMessage(error)}</p>
          <p>Try again. If this page comes back, reload the browser tab.</p>
          <button type="button" onClick={() => retry()}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
