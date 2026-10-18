import type { CSSProperties } from "react";
import type { InteractionEvent, Outcome } from "@/lib/api";
import { countOutcomes, formatDateRange, percent, zoneName } from "@/lib/format";
import styles from "./ShelfFunnel.module.css";

interface Props {
  loading: boolean;
  /** Events in the selected zone, or all events. */
  events: InteractionEvent[];
  zoneId: string | null;
  outcome: Outcome | "all";
  onSelectOutcome: (outcome: Outcome | "all") => void;
  onClearZone: () => void;
}

/** A track per final outcome: taken, put back, no pick-up. Empty tracks collapse. */
function track(count: number, min: number): string {
  return count > 0 ? `minmax(${min}px, ${count}fr)` : "0px";
}

export default function ShelfFunnel({ loading, events, zoneId, outcome, onSelectOutcome, onClearZone }: Props) {
  const counts = countOutcomes(events);
  const range = formatDateRange(events);

  const heading = (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        <h1>{zoneId ? zoneName(zoneId) : "Whole shelf"}</h1>
        {zoneId && (
          <button type="button" className={styles.clear} onClick={onClearZone}>
            Show whole shelf
          </button>
        )}
      </div>
      <p className={styles.lede}>
        A camera above this shelf records each shopper who stops. Gemini watches each clip and
        reports what they did.{" "}
        {counts.total > 0 && (
          <strong>
            {counts.total} {counts.total === 1 ? "shopper" : "shoppers"}
            {range && `, ${range}`}.
          </strong>
        )}
      </p>
    </div>
  );

  if (loading && events.length === 0) {
    return (
      <section className={styles.funnel} aria-busy="true" aria-label="Loading">
        <div className={styles.skeleton}>
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (counts.total === 0) {
    return (
      <section className={styles.funnel}>
        {heading}
        <p className={styles.empty}>No clips here yet.</p>
      </section>
    );
  }

  const tracks = (min: number) =>
    [track(counts.taken, min), track(counts.returned, min), track(counts.none, min)].join(" ");
  const chartStyle = { "--tracks": tracks(44), "--tracks-narrow": tracks(80) } as CSSProperties;

  const band = (value: Outcome | "all", count: number, label: string, className: string, rate?: number) => (
    <button
      type="button"
      className={`${styles.band} ${className}`}
      // "Stopped" resets the filter, so it never shows as pressed.
      aria-pressed={value === "all" ? undefined : outcome === value}
      aria-label={`${count} ${label}${rate !== undefined ? `, ${rate}% of picked up` : ""}. Show these clips.`}
      onClick={() => onSelectOutcome(value)}
    >
      <span className="figure">{count}</span>
      <span className={styles.label}>
        {label}
        {rate !== undefined && <span className={styles.rate}>{rate}%</span>}
      </span>
    </button>
  );

  return (
    <section className={styles.funnel}>
      {heading}
      <div className={styles.columns} aria-hidden="true">
        <span>Stopped</span>
        <span>Picked up</span>
        <span>Outcome</span>
      </div>
      <div className={styles.chart} style={chartStyle}>
        {band("all", counts.total, "stopped", styles.stopped)}
        {counts.pickedUp > 0 && (
          <div className={`${styles.band} ${styles.pickedUp}`}>
            <span className="figure">{counts.pickedUp}</span>
            <span className={styles.label}>picked up</span>
          </div>
        )}
        {counts.taken > 0 &&
          band("taken", counts.taken, "taken", styles.taken, percent(counts.taken, counts.pickedUp))}
        {counts.returned > 0 &&
          band("returned", counts.returned, "put back", styles.returned, percent(counts.returned, counts.pickedUp))}
        {counts.none > 0 && band("none", counts.none, "no pick-up", styles.none)}
      </div>
      <p className={styles.hint}>Select a band to filter clips. Percentages are of picked up.</p>
    </section>
  );
}
