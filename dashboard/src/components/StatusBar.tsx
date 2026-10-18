import styles from "./StatusBar.module.css";
import Wordmark from "./Wordmark";

/**
 * idle: no data status to show. stale: a refresh failed, the page shows older clips.
 * offline: the browser has no network connection.
 */
export type DataState = "idle" | "loading" | "live" | "stale" | "offline";

interface Props {
  state: DataState;
  /** Time of the last successful load in ms since the epoch; 0 before the first one. */
  updatedAt: number;
  /** For stale: true when the backend did not answer, false when it answered with an error. */
  unreachable?: boolean;
  onRetry?: () => void;
  retrying?: boolean;
}

function message(state: DataState, time: string | null, unreachable: boolean): string {
  const since = time ? ` Showing clips from ${time}.` : "";
  switch (state) {
    case "idle":
      return "";
    case "loading":
      return "Loading clips";
    case "live":
      return time ? `Updated ${time}` : "";
    case "stale":
      return (unreachable ? "Backend offline." : "Clips did not refresh.") + since;
    case "offline":
      return "No network connection." + since;
  }
}

export default function StatusBar({ state, updatedAt, unreachable = false, onRetry, retrying = false }: Props) {
  const time = updatedAt
    ? new Date(updatedAt).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : null;
  const problem = state === "stale" || state === "offline";

  return (
    <header className={styles.bar}>
      <Wordmark />

      <div className={styles.right}>
        <p className={problem ? styles.error : styles.status} aria-live="polite">
          {message(state, time, unreachable)}
        </p>
        {state === "stale" && onRetry && (
          <button type="button" className={styles.retry} onClick={onRetry} disabled={retrying}>
            {retrying ? "Retrying" : "Retry now"}
          </button>
        )}
      </div>
    </header>
  );
}
