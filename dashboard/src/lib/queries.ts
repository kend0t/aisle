"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { api, type ChatTurn, type InteractionEvent } from "./api";

const POLL_MS = 8000;

/** The poll interval in seconds, for messages that say how often a failed load is tried again. */
export const POLL_SECONDS = POLL_MS / 1000;

/** Stored events, polled. The backend answers 304 when nothing changed. */
export function useEvents() {
  return useQuery({
    queryKey: ["events"],
    queryFn: api.events,
    refetchInterval: POLL_MS,
    retry: false,
  });
}

/** Changes whenever an event is added or re-tagged; findings are keyed on it. */
export function eventsKey(events: InteractionEvent[]): string {
  return events
    .map((e) => `${e.event_id}:${e.created_at}:${e.conversion_outcome}:${e.items_taken_count ?? 0}:${e.behavior_tags.join(",")}`)
    .sort()
    .join("|");
}

/** Findings take a Gemini call, so they are fetched once per set of events. */
export function useInsights(events: InteractionEvent[] | undefined) {
  const key = events ? eventsKey(events) : "";
  return useQuery({
    queryKey: ["insights", key],
    queryFn: api.insights,
    enabled: events !== undefined,
    staleTime: Infinity,
    placeholderData: (previous) => previous,
    retry: false,
  });
}

export function useQuickPrompts() {
  return useQuery({ queryKey: ["quick-prompts"], queryFn: api.quickPrompts, staleTime: Infinity });
}

export function useChat() {
  return useMutation({
    mutationFn: ({ message, history }: { message: string; history: ChatTurn[] }) =>
      api.chat(message, history),
  });
}

function subscribeOnline(onChange: () => void) {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/** The browser's network status. Queries pause while offline and resume on their own. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
}
