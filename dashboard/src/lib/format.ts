import type { BehaviorTag, InteractionEvent, Outcome } from "./api";
import { ZONES } from "./zones";

export const OUTCOME_LABEL: Record<Outcome, string> = {
  taken: "Taken",
  returned: "Put back",
  none: "No pick-up",
};

export const TAG_LABEL: Record<BehaviorTag, string> = {
  phone_check: "Checked phone",
  compared_alternatives: "Compared items",
  low_shelf_reach: "Reached low shelf",
  label_inspection: "Read label",
  carried_basket: "Had basket",
  hesitated: "Hesitated",
};

/** "cereal_or_boxed_breakfast_items" and "Snacks and Candy" both become sentence case prose. */
export function humanize(value: string): string {
  const text = value.replace(/[_]+/g, " ").replace(/\s*\/\s*/g, " / ").trim().toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function zoneName(zoneId: string): string {
  return ZONES.find((z) => z.id === zoneId)?.name ?? humanize(zoneId);
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

export interface OutcomeCounts {
  total: number;
  taken: number;
  returned: number;
  none: number;
  /** Clips where an item left the shelf at some point: taken + put back. */
  pickedUp: number;
}

export function countOutcomes(events: InteractionEvent[]): OutcomeCounts {
  const taken = events.filter((e) => e.conversion_outcome === "taken").length;
  const returned = events.filter((e) => e.conversion_outcome === "returned").length;
  return {
    total: events.length,
    taken,
    returned,
    none: events.length - taken - returned,
    pickedUp: taken + returned,
  };
}

export function meanGeminiLatency(events: InteractionEvent[]): number | null {
  const values = events
    .map((e) => e.gemini_latency_ms)
    .filter((v): v is number => typeof v === "number" && v > 0);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}
