import type { InteractionEvent, Outcome } from "@/lib/api";
import { countOutcomes, humanize, OUTCOME_LABEL, TAG_LABEL, zoneName } from "@/lib/format";
import ClipThumb from "./ClipThumb";
import styles from "./ClipLog.module.css";

const FILTERS: (Outcome | "all")[] = ["all", "taken", "returned", "none"];

interface Props {
  events: InteractionEvent[];
  zoneId: string | null;
  outcome: Outcome | "all";
  onClearZone: () => void;
  onOutcomeChange: (outcome: Outcome | "all") => void;
  onOpenClip: (eventId: string) => void;
}

export default function ClipLog({
  events,
  zoneId,
  outcome,
  onClearZone,
  onOutcomeChange,
  onOpenClip,
}: Props) {
  const inZone = events.filter((e) => !zoneId || e.zone_id === zoneId);
  const shown = inZone.filter((e) => outcome === "all" || e.conversion_outcome === outcome);
  const counts = countOutcomes(inZone);
  const filterCount = { all: counts.total, taken: counts.taken, returned: counts.returned, none: counts.none };

  return (
    <section className={styles.log} aria-labelledby="clips-heading">
      <div className={styles.header}>
        <h2 id="clips-heading">
          Clips <span className={styles.count}>{shown.length}</span>
        </h2>

        <div className={styles.filters}>
          {zoneId && (
            <button type="button" className={styles.zoneChip} onClick={onClearZone}>
              {zoneName(zoneId)}
              <span aria-hidden="true">×</span>
              <span className="visually-hidden">Show all zones</span>
            </button>
          )}
          <div className={styles.segmented} role="radiogroup" aria-label="Outcome">
            {FILTERS.map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={outcome === value}
                onClick={() => onOutcomeChange(value)}
              >
                {value === "all" ? "All" : OUTCOME_LABEL[value]}{" "}
                <span className={styles.filterCount}>{filterCount[value]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {shown.length === 0 ? (
        <p className={styles.empty}>
          No clips match these filters.{" "}
          <button
            type="button"
            onClick={() => {
              onClearZone();
              onOutcomeChange("all");
            }}
          >
            Clear filters
          </button>
        </p>
      ) : (
        <ul className={styles.rows}>
          {shown.map((event) => (
            <li key={event.event_id} className={styles.row}>
              <ClipThumb eventId={event.event_id} size="m" onOpen={onOpenClip} />

              <div className={styles.body}>
                <div className={styles.topline}>
                  <span className={`${styles.outcome} ${styles[event.conversion_outcome]}`}>
                    {OUTCOME_LABEL[event.conversion_outcome]}
                  </span>
                  <span>{zoneName(event.zone_id)}</span>
                  <span>{event.zone_dwell_time_seconds} s at shelf</span>
                </div>

                <p className={styles.summary}>{event.behavioral_summary}</p>

                <div className={styles.meta}>
                  {event.behavior_tags.map((tag) => (
                    <span key={tag} className={styles.tag}>
                      {TAG_LABEL[tag] ?? humanize(tag)}
                    </span>
                  ))}
                  {event.shopper_group_size > 1 && (
                    <span className={styles.product}>{event.shopper_group_size} shoppers</span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
