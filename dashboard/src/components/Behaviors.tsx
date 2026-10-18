import type { BehaviorTag, InteractionEvent } from "@/lib/api";
import { countTags, humanize, TAG_LABEL } from "@/lib/format";
import styles from "./Behaviors.module.css";

interface Props {
  /** Events in the selected zone, or all events. */
  events: InteractionEvent[];
  tag: BehaviorTag | null;
  onSelectTag: (tag: BehaviorTag | null) => void;
}

const segments = [
  ["taken", styles.taken],
  ["returned", styles.returned],
  ["none", styles.none],
] as const;

/** What shoppers did at the shelf, split by what they left with. */
export default function Behaviors({ events, tag, onSelectTag }: Props) {
  const rows = countTags(events);
  if (rows.length === 0) return null;
  const widest = rows[0].total;

  return (
    <section className={styles.behaviors} aria-labelledby="behaviors-heading">
      <div className={styles.header}>
        <h2 id="behaviors-heading">Behaviors</h2>
        <p className={styles.note}>A clip can show more than one</p>
      </div>

      <ul className={styles.rows}>
        {rows.map((row) => {
          const label = TAG_LABEL[row.tag] ?? humanize(row.tag);
          const width = (count: number) => `${(count / widest) * 100}%`;
          return (
            <li key={row.tag}>
              <button
                type="button"
                className={styles.row}
                aria-pressed={tag === row.tag}
                aria-label={`${label}: ${row.total} clips, ${row.taken} taken, ${row.returned} put back, ${row.none} no pick-up. Show these clips.`}
                onClick={() => onSelectTag(tag === row.tag ? null : row.tag)}
              >
                <span className={styles.label}>{label}</span>
                <span className={styles.bar} aria-hidden="true">
                  {segments.map(([key, className]) =>
                    row[key] > 0 ? <span key={key} className={className} style={{ width: width(row[key]) }} /> : null,
                  )}
                </span>
                <span className={`figure ${styles.total}`}>{row.total}</span>
                <span className={styles.putBack}>{row.returned} put back</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
