"use client";

import { useState } from "react";
import { ApiError, type BehaviorTag, type InteractionEvent, type Outcome } from "@/lib/api";
import { useEvents, useInsights } from "@/lib/queries";
import StatusBar from "./StatusBar";
import ShelfFunnel from "./ShelfFunnel";
import ShelfMap from "./ShelfMap";
import Findings from "./Findings";
import Behaviors from "./Behaviors";
import ClipLog from "./ClipLog";
import ReplayDialog from "./ReplayDialog";
import CopilotLauncher from "./CopilotLauncher";
import CopilotPanel from "./CopilotPanel";
import { setCopilotExpanded, useCopilotExpanded } from "@/lib/copilotPreference";
import styles from "./Dashboard.module.css";

const NO_EVENTS: InteractionEvent[] = [];

export default function Dashboard() {
  const eventsQuery = useEvents();
  const insightsQuery = useInsights(eventsQuery.data);
  const events = eventsQuery.data ?? NO_EVENTS;
  const [zoneId, setZoneId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | "all">("all");
  const [tag, setTag] = useState<BehaviorTag | null>(null);
  const [clipId, setClipId] = useState<string | null>(null);
  const copilotExpanded = useCopilotExpanded();
  const [sheetOpen, setSheetOpen] = useState(false);

  // The zone scopes every view; outcome and behavior filter only the clip list.
  const scoped = zoneId ? events.filter((e) => e.zone_id === zoneId) : events;
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
    <div className={`${styles.shell} ${copilotExpanded ? "" : styles.collapsed}`}>
      <div className={styles.main}>
        <StatusBar
          failed={eventsQuery.isError}
          updatedAt={eventsQuery.dataUpdatedAt}
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
              events={scoped}
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
              <div className={styles.side}>
                <Findings
                  insights={insightsQuery.data ?? null}
                  loading={insightsQuery.isFetching}
                  failed={insightsQuery.isError}
                  onRetry={() => void insightsQuery.refetch()}
                  clipCount={events.length}
                  onOpenClip={setClipId}
                  onSelectZone={setZoneId}
                />
                <Behaviors events={scoped} tag={tag} onSelectTag={setTag} />
              </div>
            </div>

            {ready && (
              <ClipLog
                events={events}
                zoneId={zoneId}
                outcome={outcome}
                tag={tag}
                onClearZone={() => setZoneId(null)}
                onClearTag={() => setTag(null)}
                onOutcomeChange={setOutcome}
                onOpenClip={setClipId}
              />
            )}
          </main>
        )}
      </div>

      <CopilotPanel
        expanded={copilotExpanded}
        sheetOpen={sheetOpen}
        onHide={() => setCopilotExpanded(false)}
        onCloseSheet={() => setSheetOpen(false)}
        onOpenClip={setClipId}
      />

      <CopilotLauncher
        expanded={copilotExpanded}
        sheetOpen={sheetOpen}
        onOpen={() => {
          // One control for both layouts: the wide panel expands, the narrow sheet opens.
          setCopilotExpanded(true);
          setSheetOpen(true);
        }}
      />

      <ReplayDialog event={openClip} onClose={() => setClipId(null)} />
    </div>
  );
}
