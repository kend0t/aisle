"use client";

import { useEffect, useRef } from "react";
import { clipUrl, type InteractionEvent } from "@/lib/api";
import { formatDate, formatSeconds, humanize, TAG_LABEL, zoneName } from "@/lib/format";
import OutcomeBadge from "./OutcomeBadge";
import styles from "./ReplayDialog.module.css";

interface Props {
  event: InteractionEvent | null;
  onClose: () => void;
}

/** The structured record Gemini produced for the clip, as stored. */
function geminiRecord(event: InteractionEvent) {
  return {
    interaction_type: event.interaction_type,
    conversion_outcome: event.conversion_outcome,
    product_category_engaged: event.product_category_engaged,
    zone_dwell_time_seconds: event.zone_dwell_time_seconds,
    shopper_group_size: event.shopper_group_size,
    estimated_demographic: event.estimated_demographic,
    behavior_tags: event.behavior_tags,
    items_taken_count: event.items_taken_count ?? (event.conversion_outcome === "taken" ? 1 : 0),
    behavioral_summary: event.behavioral_summary,
  };
}

export default function ReplayDialog({ event, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (event && !dialog.open) dialog.showModal();
    if (!event && dialog.open) dialog.close();
  }, [event]);

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      onClose={onClose}
      onClick={(e) => {
        // A click on the dialog element itself is a click on the backdrop.
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby="replay-heading"
    >
      {event && (
        <div className={styles.layout}>
          <video
            key={event.event_id}
            className={styles.video}
            src={clipUrl(event.event_id)}
            controls
            preload="metadata"
            playsInline
          />

          <div className={styles.details}>
            <div className={styles.titleRow}>
              <h2 id="replay-heading">
                <OutcomeBadge outcome={event.conversion_outcome} />{" "}
                at {zoneName(event.zone_id).toLowerCase()}
              </h2>
              <button type="button" className={styles.close} onClick={onClose}>
                Close
              </button>
            </div>

            <p className={styles.summary}>{event.behavioral_summary}</p>

            {event.behavior_tags.length > 0 && (
              <ul className={styles.tags} aria-label="Behaviors Gemini saw">
                {event.behavior_tags.map((tag) => (
                  <li key={tag}>{TAG_LABEL[tag] ?? humanize(tag)}</li>
                ))}
              </ul>
            )}

            <dl className={styles.facts}>
              <div>
                <dt>Product</dt>
                <dd>{humanize(event.product_category_engaged)}</dd>
              </div>
              {event.conversion_outcome === "taken" && (
                <div>
                  <dt>Units taken</dt>
                  <dd>{event.items_taken_count ?? 1}</dd>
                </div>
              )}
              <div>
                <dt>Time at shelf</dt>
                <dd>{event.zone_dwell_time_seconds} s</dd>
              </div>
              {event.gemini_latency_ms ? (
                <div>
                  <dt>Gemini read time</dt>
                  <dd>{formatSeconds(event.gemini_latency_ms)}</dd>
                </div>
              ) : null}
              {event.total_latency_ms ? (
                <div title="From clip upload to stored record">
                  <dt>Total time</dt>
                  <dd>{formatSeconds(event.total_latency_ms)}</dd>
                </div>
              ) : null}
              <div>
                <dt>Date</dt>
                <dd>{formatDate(event.timestamp)}</dd>
              </div>
              <div>
                <dt>Clip</dt>
                <dd>{event.event_id}</dd>
              </div>
            </dl>

            <details className={styles.record}>
              <summary>How Gemini read this clip</summary>
              <pre>{JSON.stringify(geminiRecord(event), null, 2)}</pre>
            </details>
          </div>
        </div>
      )}
    </dialog>
  );
}
