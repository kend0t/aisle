"use client";

import { useSyncExternalStore } from "react";

/*
  Whether the Copilot panel is expanded on wide screens, remembered per browser.
  Storage can be unavailable (private windows, blocked site data); the panel then
  starts expanded and the choice lasts for the session only.
*/

const KEY = "aisle.copilot.expanded";
const listeners = new Set<() => void>();
let fallback = true;

function read(): boolean {
  try {
    const stored = window.localStorage.getItem(KEY);
    return stored === null ? fallback : stored === "true";
  } catch {
    return fallback;
  }
}

export function setCopilotExpanded(expanded: boolean) {
  fallback = expanded;
  try {
    window.localStorage.setItem(KEY, String(expanded));
  } catch {
    // Keep the in-memory value only.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useCopilotExpanded(): boolean {
  return useSyncExternalStore(subscribe, read, () => true);
}
