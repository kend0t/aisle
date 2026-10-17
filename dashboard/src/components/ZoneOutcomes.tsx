import type { InteractionEvent, Outcome } from "@/lib/api";
import { countOutcomes, OUTCOME_LABEL, type OutcomeCounts } from "@/lib/format";
import { ZONES } from "@/lib/zones";
import styles from "./ZoneOutcomes.module.css";

const SEGMENTS: { outcome: Outcome; key: keyof OutcomeCounts }[] = [
  { outcome: "taken", key: "taken" },
  { outcome: "returned", key: "returned" },
  { outcome: "none", key: "none" },
];

interface Props {
  events: InteractionEvent[];
  selectedZone: string | null;
  onSelectZone: (zoneId: string) => void;
  onSelectOutcome: (outcome: Outcome) => void;
}

export default function ZoneOutcomes({ events, selectedZone, onSelectZone, onSelectOutcome }: Props) {
  const rows = ZONES.map((zone) => ({
    zone,
    counts: countOutcomes(events.filter((e) => e.zone_id === zone.id)),
  }));
  const max = Math.max(1, ...rows.map((r) => r.counts.total));

  return (
    <section className={styles.outcomes} aria-labelledby="outcomes-heading">
      <div className={styles.header}>
        <h2 id="outcomes-heading">What happened at each bay</h2>
        <ul className={styles.legend}>
          {SEGMENTS.map(({ outcome }) => (
            <li key={outcome}>
              <span className={`${styles.swatch} ${styles[outcome]}`} aria-hidden="true" />
              {OUTCOME_LABEL[outcome]}
            </li>
          ))}
        </ul>
      </div>

      <div className={styles.rows}>
        {rows.map(({ zone, counts }) => (
          <div
            key={zone.id}
            className={`${styles.row} ${selectedZone === zone.id ? styles.selected : ""}`}
          >
            <button type="button" className={styles.zoneName} onClick={() => onSelectZone(zone.id)}>
              {zone.name}
              <span>
                {counts.total} clips, {counts.averageDwell.toFixed(1)} s at shelf on average
              </span>
            </button>

            <div className={styles.bar} style={{ width: `${(counts.total / max) * 100}%` }}>
              {SEGMENTS.map(({ outcome, key }) => {
                const value = counts[key];
                if (!value) return null;
                return (
                  <button
                    key={outcome}
                    type="button"
                    className={`${styles.segment} ${styles[outcome]}`}
                    style={{ flexGrow: value }}
                    onClick={() => {
                      if (selectedZone !== zone.id) onSelectZone(zone.id);
                      onSelectOutcome(outcome);
                    }}
                    aria-label={`${zone.name}: ${value} ${OUTCOME_LABEL[outcome].toLowerCase()}. Show these clips.`}
                  >
                    <span className="figure">{value}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
