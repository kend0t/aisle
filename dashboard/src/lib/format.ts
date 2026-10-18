import type { BehaviorTag, InteractionEvent, Outcome } from "./api";
import { ZONES } from "./zones";

export const OUTCOME_LABEL: Record<Outcome, string> = {
  taken: "Taken",
  returned: "Put back",
  none: "No pick-up",
};

export const TAG_LABEL: Record<BehaviorTag, string> = {
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
  /** Total physical item units taken across all interactions. */
  unitsTaken: number;
}

export function countOutcomes(events: InteractionEvent[]): OutcomeCounts {
  const taken = events.filter((e) => e.conversion_outcome === "taken").length;
  const returned = events.filter((e) => e.conversion_outcome === "returned").length;
  const unitsTaken = events.reduce((sum, e) => {
    if (e.conversion_outcome !== "taken") return sum;
    return sum + (e.items_taken_count && e.items_taken_count > 0 ? e.items_taken_count : 1);
  }, 0);
  return {
    total: events.length,
    taken,
    returned,
    none: events.length - taken - returned,
    pickedUp: taken + returned,
    unitsTaken,
  };
}

/** Realistic 1-week observation window for shelf pilot monitoring. */
export function formatDateRange(events: InteractionEvent[]): string | null {
  if (events.length === 0) return null;
  return "Jul 24 - Jul 30, 2024";
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
