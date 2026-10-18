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

/** "16 May - 30 Jul 2024"; the year appears once when both ends share it. */
export function formatDateRange(events: InteractionEvent[]): string | null {
  const times = events.map((e) => new Date(e.timestamp).getTime()).filter((t) => !Number.isNaN(t));
  if (times.length === 0) return null;
  const first = new Date(Math.min(...times));
  const last = new Date(Math.max(...times));
  const dayMonth = { day: "numeric", month: "short" } as const;
  const end = last.toLocaleDateString(undefined, { ...dayMonth, year: "numeric" });
  if (first.toDateString() === last.toDateString()) return end;
  const start = first.toLocaleDateString(
    undefined,
    first.getFullYear() === last.getFullYear() ? dayMonth : { ...dayMonth, year: "numeric" },
  );
  return `${start} - ${end}`;
}

export interface TagCounts extends OutcomeCounts {
  tag: BehaviorTag;
}

/** Outcome counts per behavior, most frequent first. A clip can count under several behaviors. */
export function countTags(events: InteractionEvent[]): TagCounts[] {
  const tags = [...new Set(events.flatMap((e) => e.behavior_tags))];
  return tags
    .map((tag) => ({ tag, ...countOutcomes(events.filter((e) => e.behavior_tags.includes(tag))) }))
    .sort((a, b) => b.total - a.total);
}
