"use client";

import { useState } from "react";
import { isUnreachable, type BehaviorTag, type InteractionEvent, type Outcome } from "@/lib/api";
import { POLL_SECONDS, useEvents, useInsights, useOnline } from "@/lib/queries";
import StatusBar, { type DataState } from "./StatusBar";
import PageMessage from "./PageMessage";
import SectionBoundary from "./SectionBoundary";
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
  const eventsQuery = useEvents();  const insightsQuery = useInsights(eventsQuery.data);
  const online = useOnline();
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
  const unreachable = isUnreachable(error);
  const retryEvents = () => void eventsQuery.refetch();

  // Before the first load, a failure takes the whole page; after it, only the status line.
  const dataState: DataState = !online
    ? "offline"
    : ready
      ? error
        ? "stale"
        : "live"
      : error
        ? "idle"
        : "loading";

  const toggleZone = (id: string) => setZoneId((current) => (current === id ? null : id));

  return (
    <div className={`${styles.shell} ${copilotExpanded ? "" : styles.collapsed}`}>
      <div className={styles.main}>
        <StatusBar
          state={dataState}
          updatedAt={eventsQuery.dataUpdatedAt}
          unreachable={unreachable}
          onRetry={retryEvents}
          retrying={eventsQuery.isFetching}
        />

        {!ready && !online ? (
          <PageMessage title="No network connection.">
            <p>Clips load when the connection comes back.</p>
          </PageMessage>
        ) : !ready && error ? (
          <PageMessage
            title={unreachable ? "Backend offline." : "Clips did not load."}
            actions={
              <button type="button" onClick={retryEvents} disabled={eventsQuery.isFetching}>
                {eventsQuery.isFetching ? "Retrying" : "Retry now"}
              </button>
            }
          >
            <p>{error.message}</p>
            <p>Trying again every {POLL_SECONDS} s.</p>
            {unreachable && process.env.NODE_ENV === "development" && (
              <p>
                Start it with <code>uv run uvicorn backend_service.main:app --port 8000</code>
              </p>
            )}
          </PageMessage>
        ) : (
          <main className={styles.content}>
            <SectionBoundary name="Shelf funnel">
              <ShelfFunnel
                loading={eventsQuery.isPending}
                events={scoped}
                zoneId={zoneId}
                outcome={outcome}
                onSelectOutcome={setOutcome}
                onClearZone={() => setZoneId(null)}
              />
            </SectionBoundary>

            <div className={styles.hero}>
              <SectionBoundary name="Shelf map">
                <ShelfMap
                  ready={ready}
                  events={events}
                  selectedZone={zoneId}
                  attentionZones={attentionZones}
                  onSelectZone={toggleZone}
                />
              </SectionBoundary>
              <div className={styles.side}>
                <SectionBoundary name="Findings">
                  <Findings
                    insights={insightsQuery.data ?? null}
                    waiting={!ready}
                    loading={insightsQuery.isFetching}
                    updating={insightsQuery.isFetching && insightsQuery.isPlaceholderData}
                    error={insightsQuery.error}
                    onRetry={() => void insightsQuery.refetch()}
                    clipCount={events.length}
                    onOpenClip={setClipId}
                    onSelectZone={setZoneId}
                  />
                </SectionBoundary>
                <SectionBoundary name="Behaviors">
                  <Behaviors loading={!ready} events={scoped} tag={tag} onSelectTag={setTag} />
                </SectionBoundary>
              </div>
            </div>

            <SectionBoundary name="Clip list">
              <ClipLog
                ready={ready}
                events={events}
                zoneId={zoneId}
                outcome={outcome}
                tag={tag}
                onClearZone={() => setZoneId(null)}
                onClearTag={() => setTag(null)}
                onOutcomeChange={setOutcome}
                onOpenClip={setClipId}
              />
            </SectionBoundary>
          </main>
        )}
      </div>

      <SectionBoundary name="Copilot">
        <CopilotPanel
          expanded={copilotExpanded}
          sheetOpen={sheetOpen}
          onHide={() => setCopilotExpanded(false)}
          onCloseSheet={() => setSheetOpen(false)}
          onOpenClip={setClipId}
        />
      </SectionBoundary>

      <CopilotLauncher
        expanded={copilotExpanded}
        sheetOpen={sheetOpen}
        onOpen={() => {
          // One control for both layouts: the wide panel expands, the narrow sheet opens.
          setCopilotExpanded(true);
          setSheetOpen(true);
        }}
      />

      <SectionBoundary name="Clip replay">
        <ReplayDialog event={openClip} onClose={() => setClipId(null)} />
      </SectionBoundary>
    </div>
  );
}
