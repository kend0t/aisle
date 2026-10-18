import styles from "./StatusBar.module.css";
import Wordmark from "./Wordmark";

interface Props {
  failed: boolean;
  /** Time of the last successful load in ms since the epoch; 0 before the first one. */
  updatedAt: number;
}

export default function StatusBar({ failed, updatedAt }: Props) {
  const updated = updatedAt
    ? new Date(updatedAt).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <header className={styles.bar}>
      <Wordmark />

      <p className={failed ? styles.error : styles.status} aria-live="polite">
        {failed ? "Backend offline, retrying" : updated ? `Updated ${updated}` : "Loading"}
      </p>
    </header>
  );
}
