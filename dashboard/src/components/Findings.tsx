import type { Finding, FindingSeverity, InsightsResponse, InteractionEvent } from "@/lib/api";
import { retryInsights, type DashboardState } from "@/lib/dashboardStore";
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
  status: DashboardState["insightsStatus"];
  events: InteractionEvent[];
  onOpenClip: (eventId: string) => void;
  onSelectZone: (zoneId: string) => void;
}

export default function Findings({ insights, status, events, onOpenClip, onSelectZone }: Props) {
  const showLoading = status === "loading" && !insights;

  return (
    <section className={styles.findings} aria-labelledby="findings-heading" aria-busy={showLoading}>
      <div className={styles.header}>
        <h2 id="findings-heading">What to look at</h2>
        {insights && (
          <p className={styles.source}>
            {insights.source === "gemini"
              ? `Gemini, ${insights.event_count} clips`
              : "Rule-based, Gemini unavailable"}
          </p>
        )}
      </div>

      {showLoading && (
        <div className={styles.loading}>
          <p>Reading {events.length} clips, about 30 s</p>
          <span className={styles.skeleton} />
          <span className={styles.skeleton} />
          <span className={styles.skeleton} />
        </div>
      )}

      {status === "error" && !insights && (
        <div className={styles.failed}>
          <p>Findings did not load.</p>
          <button type="button" onClick={retryInsights}>
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
