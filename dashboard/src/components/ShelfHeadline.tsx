import { percent, type OutcomeCounts } from "@/lib/format";
import styles from "./ShelfHeadline.module.css";

interface Props {
  totals: OutcomeCounts;
  loading: boolean;
}

export default function ShelfHeadline({ totals, loading }: Props) {
  if (loading && totals.total === 0) {
    return (
      <section className={styles.headline} aria-busy="true">
        <h1 className={styles.loading}>Reading the shelf</h1>
      </section>
    );
  }

  return (
    <section className={styles.headline}>
      <h1>
        <span className={`figure ${styles.big} ${styles.putBack}`}>{totals.returned}</span> of{" "}
        <span className={`figure ${styles.big}`}>{totals.pickedUp}</span> items picked up went back on the shelf
      </h1>
      <dl className={styles.supporting}>
        <div>
          <dt>Taken</dt>
          <dd>
            <span className="figure">{percent(totals.taken, totals.total)}%</span> of{" "}
            {totals.total} clips ended with the item kept
          </dd>
        </div>
        <div>
          <dt>Put back</dt>
          <dd>
            <span className="figure">{percent(totals.returned, totals.pickedUp)}%</span> of items
            picked up were returned
          </dd>
        </div>
        <div>
          <dt>Time at shelf</dt>
          <dd>
            <span className="figure">{totals.averageDwell.toFixed(1)} s</span> on average per clip
          </dd>
        </div>
      </dl>
    </section>
  );
}
