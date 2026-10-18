import type { BehaviorTag, InteractionEvent, Outcome } from "@/lib/api";
import { countOutcomes, humanize, OUTCOME_LABEL, TAG_LABEL, zoneName } from "@/lib/format";
import ClipThumb from "./ClipThumb";
import OutcomeBadge from "./OutcomeBadge";
import styles from "./ClipLog.module.css";

const FILTERS: (Outcome | "all")[] = ["all", "taken", "returned", "none"];

interface Props {
  ready: boolean;
  events: InteractionEvent[];
  zoneId: string | null;
  outcome: Outcome | "all";
  tag: BehaviorTag | null;
  onClearZone: () => void;
  onClearTag: () => void;
  onOutcomeChange: (outcome: Outcome | "all") => void;
  onOpenClip: (eventId: string) => void;
}

export default function ClipLog({
  ready,
  events,
  zoneId,
  outcome,
  tag,
  onClearZone,
  onClearTag,
  onOutcomeChange,
  onOpenClip,
}: Props) {
  // Zone and behavior narrow the set; the outcome filter then splits it, so its counts sum to "All".
  const scoped = events.filter(
    (e) => (!zoneId || e.zone_id === zoneId) && (!tag || e.behavior_tags.includes(tag)),
  );
  const shown = scoped.filter((e) => outcome === "all" || e.conversion_outcome === outcome);
  const counts = countOutcomes(scoped);
  const filterCount = { all: counts.total, taken: counts.taken, returned: counts.returned, none: counts.none };

  if (!ready) {
    return (
      <section className={styles.log} aria-labelledby="clips-heading" aria-busy="true">
        <div className={styles.header}>
          <h2 id="clips-heading">Clips</h2>
        </div>
        <p className="visually-hidden">Loading the clip list</p>
        <ul className={styles.rows} aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className={styles.row}>
              <span className={`skeleton ${styles.thumbSkeleton}`} />
              <div className={styles.body}>
                <span className={`skeleton ${styles.lineSkeleton}`} />
                <span className={`skeleton ${styles.lineSkeleton} ${styles.long}`} />
              </div>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  return (
    <section className={styles.log} aria-labelledby="clips-heading">
      <div className={styles.header}>
        <h2 id="clips-heading">
          Clips <span className={styles.count}>{shown.length}</span>
        </h2>

        <div className={styles.filters}>
          {zoneId && (
            <button type="button" className={styles.chip} onClick={onClearZone}>
              {zoneName(zoneId)}
              <span aria-hidden="true">×</span>
              <span className="visually-hidden">Show all zones</span>
            </button>
          )}
          {tag && (
            <button type="button" className={styles.chip} onClick={onClearTag}>
              {TAG_LABEL[tag] ?? humanize(tag)}
              <span aria-hidden="true">×</span>
              <span className="visually-hidden">Show all behaviors</span>
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

      {events.length === 0 ? (
        <p className={styles.empty}>No clips stored yet. New clips appear here as the camera sends them.</p>
      ) : shown.length === 0 ? (
        <p className={styles.empty}>
          No clips match these filters.{" "}
          <button
            type="button"
            onClick={() => {
              onClearZone();
              onClearTag();
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
                  <OutcomeBadge outcome={event.conversion_outcome} />
                  {event.conversion_outcome === "taken" && (event.items_taken_count ?? 1) > 1 && (
                    <span className={styles.product}>
                      {event.items_taken_count} units taken
                    </span>
                  )}
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
