import type { InteractionEvent } from "@/lib/api";
import { countOutcomes, percent } from "@/lib/format";
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
  const zones = ZONES.map((zone) => {
    const counts = countOutcomes(events.filter((e) => e.zone_id === zone.id));
    return { zone, counts, rate: percent(counts.returned, counts.pickedUp) };
  });

  return (
    <figure className={styles.map}>
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
          {zones.map(({ zone, rate }) => (
            <polygon
              key={zone.id}
              points={zone.polygon.map((p) => p.join(",")).join(" ")}
              className={selectedZone === zone.id ? styles.zoneSelected : styles.zone}
              style={{ fillOpacity: 0.12 + (rate / 100) * 0.5 }}
              onClick={() => onSelectZone(zone.id)}
            />
          ))}
        </svg>

        {ready && zones.map(({ zone, counts, rate }) => {
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
              <span className={`figure ${styles.labelRate}`}>{rate}%</span>
              <span className={styles.labelDetail}>
                put back, {counts.returned} of {counts.pickedUp} picked up
              </span>
            </button>
          );
        })}
      </div>
      <figcaption className={styles.caption}>
        The edge camera watches the floor in front of each bay. Darker red means more items put
        back. Select a zone to filter the clips.
      </figcaption>
    </figure>
  );
}
