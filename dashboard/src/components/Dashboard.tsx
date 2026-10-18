"use client";

import { useState } from "react";
import { ApiError, type InteractionEvent, type Outcome } from "@/lib/api";
import { useEvents, useInsights } from "@/lib/queries";
import StatusBar from "./StatusBar";
import ShelfFunnel from "./ShelfFunnel";
import ShelfMap from "./ShelfMap";
import Findings from "./Findings";
import ClipLog from "./ClipLog";
import ReplayDialog from "./ReplayDialog";
import CopilotPanel from "./CopilotPanel";
import styles from "./Dashboard.module.css";

const NO_EVENTS: InteractionEvent[] = [];

export default function Dashboard() {
  const eventsQuery = useEvents();
  const insightsQuery = useInsights(eventsQuery.data);
  const events = eventsQuery.data ?? NO_EVENTS;
  const [zoneId, setZoneId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | "all">("all");
  const [clipId, setClipId] = useState<string | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);

  const openClip = events.find((e) => e.event_id === clipId) ?? null;
  const attentionZones = (insightsQuery.data?.findings ?? [])
    .filter((f) => f.severity === "act" && f.zone_id)
    .map((f) => f.zone_id as string);

  const ready = eventsQuery.data !== undefined;
  const error = eventsQuery.error;
  // No HTTP status means the backend did not answer; a status means it answered with an error.
  const offline = !(error instanceof ApiError && error.status !== undefined);

  const toggleZone = (id: string) => setZoneId((current) => (current === id ? null : id));

  return (
    <div className={styles.shell}>
      <div className={styles.main}>
        <StatusBar
          events={events}
          failed={eventsQuery.isError}
          updatedAt={eventsQuery.dataUpdatedAt}
          onOpenCopilot={() => setCopilotOpen(true)}
        />

        {error && !ready ? (
          <section className={styles.offline} aria-live="polite">
            <h1>{offline ? "Backend offline. Retrying." : "Data not available. Retrying."}</h1>
            <p>{error.message}</p>
            {offline && process.env.NODE_ENV === "development" && (
              <p>
                <code>uv run uvicorn backend_service.main:app --port 8000</code>
              </p>
            )}
          </section>
        ) : (
          <main className={styles.content}>
            <ShelfFunnel
              loading={eventsQuery.isPending}
              events={events}
              zoneId={zoneId}
              outcome={outcome}
              onSelectOutcome={setOutcome}
              onClearZone={() => setZoneId(null)}
            />

            <div className={styles.hero}>
              <ShelfMap
                ready={ready}
                events={events}
                selectedZone={zoneId}
                attentionZones={attentionZones}
                onSelectZone={toggleZone}
              />
              <Findings
                insights={insightsQuery.data ?? null}
                loading={insightsQuery.isFetching}
                failed={insightsQuery.isError}
                onRetry={() => void insightsQuery.refetch()}
                clipCount={events.length}
                onOpenClip={setClipId}
                onSelectZone={setZoneId}
              />
            </div>

            {ready && (
              <ClipLog
                events={events}
                zoneId={zoneId}
                outcome={outcome}
                onClearZone={() => setZoneId(null)}
                onOutcomeChange={setOutcome}
                onOpenClip={setClipId}
              />
            )}
          </main>
        )}
      </div>

      <CopilotPanel
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        onOpenClip={setClipId}
      />

      <ReplayDialog event={openClip} onClose={() => setClipId(null)} />
    </div>
  );
}
