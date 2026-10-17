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
        {latency !== null && (
          <div title="Mean time Gemini takes to read one clip, measured per clip">
            <dt>Gemini</dt>
            <dd>{formatSeconds(latency)} per clip</dd>
          </div>
        )}
        <div aria-live="polite">
          <dt className="visually-hidden">Status</dt>
          <dd className={data.status === "error" ? styles.error : undefined}>
            {data.status === "error"
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
