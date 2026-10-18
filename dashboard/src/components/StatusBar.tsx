import type { InteractionEvent } from "@/lib/api";
import { formatSeconds, meanGeminiLatency } from "@/lib/format";
import styles from "./StatusBar.module.css";

interface Props {
  events: InteractionEvent[];
  failed: boolean;
  /** Time of the last successful load in ms since the epoch; 0 before the first one. */
  updatedAt: number;
  onOpenCopilot: () => void;
}

export default function StatusBar({ events, failed, updatedAt, onOpenCopilot }: Props) {
  const latency = meanGeminiLatency(events);
  const updated = updatedAt
    ? new Date(updatedAt).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.wordmark}>AIsle</span>
        <span className={styles.store}>Test shelf, MERL dataset</span>
      </div>

      <dl className={styles.facts}>
        {latency !== null && (
          <div title="Mean time Gemini takes to read one clip, measured per clip">
            <dt>Gemini</dt>
            <dd>{formatSeconds(latency)} per clip</dd>
          </div>
        )}
        <div aria-live="polite">
          <dt className="visually-hidden">Status</dt>
          <dd className={failed ? styles.error : undefined}>
            {failed
              ? "Backend offline, retrying"
              : updated
                ? `Updated ${updated}`
                : "Loading"}
          </dd>
        </div>
      </dl>

      <button type="button" className={styles.copilotButton} onClick={onOpenCopilot}>
        Ask about this shelf
      </button>
    </header>
  );
}
