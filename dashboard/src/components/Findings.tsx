import { errorMessage, type Finding, type FindingSeverity, type InsightsResponse } from "@/lib/api";
import { zoneName } from "@/lib/format";
import ClipThumb from "./ClipThumb";
import styles from "./Findings.module.css";

const SEVERITY_LABEL: Record<FindingSeverity, string> = {
  act: "Act on this",
  watch: "Watch",
  info: "Context",
};

/** Findings made before `action` existed end `detail` with the action; show that last sentence. */
function actionText(finding: Finding): string {
  if (finding.action) return finding.action;
  const sentences = finding.detail.match(/[^.!?]+[.!?]+/g);
  return sentences?.at(-1)?.trim() ?? finding.detail;
}

const MAX_THUMBS = 4;

interface Props {
  insights: InsightsResponse | null;
  /** Clips have not loaded yet, so findings have not been asked for. */
  waiting: boolean;
  loading: boolean;
  /** Earlier findings are shown while new ones are read for changed clips. */
  updating: boolean;
  error: Error | null;
  onRetry: () => void;
  clipCount: number;
  onOpenClip: (eventId: string) => void;
  onSelectZone: (zoneId: string) => void;
}

export default function Findings({
  insights,
  waiting,
  loading,
  updating,
  error,
  onRetry,
  clipCount,
  onOpenClip,
  onSelectZone,
}: Props) {
  const showLoading = waiting || (loading && !insights);
  const failed = error !== null && !loading;

  return (
    <section className={styles.findings} aria-labelledby="findings-heading" aria-busy={showLoading || updating}>
      <div className={styles.header}>
        <h2 id="findings-heading">What to look at</h2>
        <p className={styles.source} aria-live="polite">
          {updating
            ? `Reading ${clipCount} clips again, about 30 s`
            : insights
              ? insights.source === "gemini"
                ? `Gemini, ${insights.event_count} clips`
                : "Rule-based, Gemini unavailable"
              : null}
        </p>
      </div>

      {showLoading && (
        <div className={styles.loading} role="status">
          <p>{waiting ? "Waiting for clips" : `Reading ${clipCount} clips, about 30 s`}</p>
          <span className={`skeleton ${styles.skeleton}`} />
          <span className={`skeleton ${styles.skeleton}`} />
          <span className={`skeleton ${styles.skeleton}`} />
        </div>
      )}

      {failed && (
        <div className={styles.failed} role="alert">
          <p>
            {insights ? "Findings did not refresh. These are from earlier clips." : "Findings did not load."}{" "}
            {errorMessage(error)}
          </p>
          <button type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {insights && insights.findings.length === 0 && (
        <p className={styles.empty}>No findings yet.</p>
      )}

      {insights && insights.findings.length > 0 && (
        <ol className={styles.list}>
          {insights.findings.map((finding, index) => {
            const extra = finding.evidence_event_ids.length - MAX_THUMBS;
            return (
              <li key={index} className={`${styles.item} ${styles[finding.severity]}`}>
                <h3>
                  <span className="visually-hidden">{SEVERITY_LABEL[finding.severity]}: </span>
                  {finding.title}
                </h3>
                <p className={styles.action}>{actionText(finding)}</p>

                {finding.evidence_event_ids.length > 0 && (
                  <div className={styles.evidence}>
                    {finding.evidence_event_ids.slice(0, MAX_THUMBS).map((id) => (
                      <ClipThumb key={id} eventId={id} size="s" onOpen={onOpenClip} />
                    ))}
                    {extra > 0 && <span className={styles.more}>{extra} more</span>}
                  </div>
                )}

                {finding.zone_id && (
                  <button
                    type="button"
                    className={styles.zoneLink}
                    onClick={() => onSelectZone(finding.zone_id as string)}
                  >
                    {zoneName(finding.zone_id)}
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
