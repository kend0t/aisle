"use client";

import { useSyncExternalStore } from "react";
import {
  api,
  ApiError,
  type AnalyticsSummary,
  type InsightsResponse,
  type InteractionEvent,
  type QuickPrompt,
} from "./api";

const POLL_MS = 8000;

export interface DashboardState {
  status: "loading" | "ready" | "error";
  error: string | null;
  updatedAt: Date | null;
  summary: AnalyticsSummary | null;
  events: InteractionEvent[];
  insights: InsightsResponse | null;
  insightsStatus: "idle" | "loading" | "ready" | "error";
  quickPrompts: QuickPrompt[];
}

const initialState: DashboardState = {
  status: "loading",
  error: null,
  updatedAt: null,
  summary: null,
  events: [],
  insights: null,
  insightsStatus: "idle",
  quickPrompts: [],
};

let state = initialState;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;
let insightsKey = "";

function setState(patch: Partial<DashboardState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

function eventsKey(events: InteractionEvent[]): string {
  return events
    .map((e) => `${e.event_id}:${e.created_at}:${e.behavior_tags.join(",")}`)
    .sort()
    .join("|");
}

async function loadInsights(key: string) {
  insightsKey = key;
  setState({ insightsStatus: "loading" });
  try {
    const insights = await api.insights();
    if (insightsKey === key) setState({ insights, insightsStatus: "ready" });
  } catch {
    if (insightsKey === key) setState({ insightsStatus: "error" });
  }
}

export async function refresh() {
  try {
    const [summary, events] = await Promise.all([api.summary(), api.events()]);
    setState({ summary, events, status: "ready", error: null, updatedAt: new Date() });

    // Findings take a Gemini call, so only ask again when the stored events change.
    const key = eventsKey(events);
    if (key !== insightsKey) void loadInsights(key);
  } catch (err) {
    setState({
      status: "error",
      error: err instanceof ApiError ? err.message : "The dashboard could not load data.",
    });
  }
}

export function retryInsights() {
  void loadInsights(eventsKey(state.events));
}

async function loadQuickPrompts() {
  try {
    setState({ quickPrompts: await api.quickPrompts() });
  } catch {
    // Copilot still works without suggested prompts.
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) {
    void refresh();
    void loadQuickPrompts();
    timer = setInterval(refresh, POLL_MS);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

export function useDashboard(): DashboardState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => initialState,
  );
}
