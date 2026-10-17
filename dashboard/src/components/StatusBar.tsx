import type { DashboardState } from "@/lib/dashboardStore";
import { formatSeconds, meanGeminiLatency } from "@/lib/format";
import styles from "./StatusBar.module.css";

interface Props {
  data: DashboardState;
  onOpenCopilot: () => void;
}

export default function StatusBar({ data, onOpenCopilot }: Props) {
  const latency = meanGeminiLatency(data.events);
  const updated = data.updatedAt?.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.wordmark}>AIsle</span>
        <span className={styles.store}>Test shelf, MERL dataset</span>
      </div>

      <dl className={styles.facts}>
        <div>
          <dt>Clips analyzed</dt>
          <dd>{data.events.length}</dd>
        </div>
        {latency !== null && (
          <div title="Mean time Gemini takes to read one clip, measured per clip">
            <dt>Gemini read time</dt>
            <dd>{formatSeconds(latency)}</dd>
          </div>
        )}
        <div aria-live="polite">
          <dt>Data</dt>
          <dd className={data.status === "error" ? styles.error : undefined}>
            {data.status === "error"
              ? "Backend not reachable, retrying"
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
