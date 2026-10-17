import type { CSSProperties } from "react";
import type { InteractionEvent, Outcome } from "@/lib/api";
import { countOutcomes, percent, zoneName } from "@/lib/format";
import styles from "./ShelfFunnel.module.css";

interface Props {
  loading: boolean;
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
  const scoped = zoneId ? events.filter((e) => e.zone_id === zoneId) : events;
  const counts = countOutcomes(scoped);

  const heading = (
    <div className={styles.header}>
      <h1>{zoneId ? zoneName(zoneId) : "Whole shelf"}</h1>
      {zoneId && (
        <button type="button" className={styles.clear} onClick={onClearZone}>
          Show whole shelf
        </button>
      )}
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

  // The put-back track keeps a minimum so the callout beside it always has room.
  const tracks = (min: number, calloutMin: number) =>
    [
      track(counts.taken, min),
      counts.returned > 0 ? `minmax(${calloutMin}px, ${counts.returned}fr)` : `${calloutMin}px`,
      track(counts.none, min),
    ].join(" ");
  const chartStyle = { "--tracks": tracks(44, 64), "--tracks-narrow": tracks(80, 80) } as CSSProperties;

  const band = (value: Outcome | "all", count: number, label: string, className: string) => (
    <button
      type="button"
      className={`${styles.band} ${className}`}
      // "Stopped" resets the filter, so it never shows as pressed.
      aria-pressed={value === "all" ? undefined : outcome === value}
      aria-label={`${count} ${label}. Show these clips.`}
      onClick={() => onSelectOutcome(value)}
    >
      <span className="figure">{count}</span> {label}
    </button>
  );

  return (
    <section className={styles.funnel}>
      {heading}
      <div className={styles.chart} style={chartStyle}>
        {band("all", counts.total, "stopped", styles.stopped)}
        {counts.pickedUp > 0 && (
          <div className={`${styles.band} ${styles.pickedUp}`}>
            <span className="figure">{counts.pickedUp}</span> picked up
          </div>
        )}
        {counts.none > 0 && band("none", counts.none, "no pick-up", styles.none)}
        {counts.taken > 0 && band("taken", counts.taken, "taken", styles.taken)}
        {counts.returned > 0 && band("returned", counts.returned, "put back", styles.returned)}

        <p className={styles.callout}>
          <span className={`figure ${styles.calloutFigure}`}>{counts.returned}</span>
          <span>
            put back
            {counts.pickedUp > 0 && (
              <span className={styles.rate}>
                {percent(counts.returned, counts.pickedUp)}% of picked up
              </span>
            )}
          </span>
        </p>
      </div>
    </section>
  );
}
