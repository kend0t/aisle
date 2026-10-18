import type { InteractionEvent } from "@/lib/api";
import { countOutcomes } from "@/lib/format";
import { FRAME_HEIGHT, FRAME_WIDTH, ZONES, zoneCentroid } from "@/lib/zones";
import styles from "./ShelfMap.module.css";

interface Props {
  ready: boolean;
  events: InteractionEvent[];
  selectedZone: string | null;
  attentionZones: string[];
  onSelectZone: (zoneId: string) => void;
}

export default function ShelfMap({ ready, events, selectedZone, attentionZones, onSelectZone }: Props) {
  const zones = ZONES.map((zone) => ({
    zone,
    counts: countOutcomes(events.filter((e) => e.zone_id === zone.id)),
  }));

  return (
    <figure className={styles.map} aria-label="Shelf map. Select a zone to filter.">
      <div className={styles.frame}>
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size local still, no optimization needed */}
        <img
          src="/shelf-frame.jpg"
          width={FRAME_WIDTH}
          height={FRAME_HEIGHT}
          alt="Overhead camera view of a cereal bay and a snack bay"
        />
        <svg
          className={styles.overlay}
          viewBox={`0 0 ${FRAME_WIDTH} ${FRAME_HEIGHT}`}
          aria-hidden="true"
        >
          {zones.map(({ zone }) => (
            <polygon
              key={zone.id}
              points={zone.polygon.map((p) => p.join(",")).join(" ")}
              className={selectedZone === zone.id ? styles.zoneSelected : styles.zone}
              onClick={() => onSelectZone(zone.id)}
            />
          ))}
        </svg>

        {ready && zones.map(({ zone, counts }) => {
          const [cx, cy] = zoneCentroid(zone);
          const attention = attentionZones.includes(zone.id);
          return (
            <button
              key={zone.id}
              type="button"
              className={`${styles.label} ${attention ? styles.attention : ""}`}
              style={{ left: `${(cx / FRAME_WIDTH) * 100}%`, top: `${(cy / FRAME_HEIGHT) * 100}%` }}
              aria-pressed={selectedZone === zone.id}
              onClick={() => onSelectZone(zone.id)}
            >
              <span className={styles.labelName}>{zone.name}</span>
              <span className={styles.labelTotal}>
                <span className={`figure ${styles.labelFigure}`}>{counts.total}</span> stopped
              </span>
              <span className={styles.labelSplit}>
                <span className={styles.labelTaken}>
                  <span className="figure">{counts.taken}</span> taken
                </span>
                <span className={styles.labelReturned}>
                  <span className="figure">{counts.returned}</span> put back
                </span>
                <span>
                  <span className="figure">{counts.none}</span> no pick-up
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </figure>
  );
}
