"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/lib/dashboardStore";
import { countOutcomes } from "@/lib/format";
import type { Outcome } from "@/lib/api";
import StatusBar from "./StatusBar";
import ShelfHeadline from "./ShelfHeadline";
import ShelfMap from "./ShelfMap";
import Findings from "./Findings";
import ZoneOutcomes from "./ZoneOutcomes";
import ClipLog from "./ClipLog";
import ReplayDialog from "./ReplayDialog";
import CopilotPanel from "./CopilotPanel";
import styles from "./Dashboard.module.css";

export default function Dashboard() {
  const data = useDashboard();
  const [zoneId, setZoneId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | "all">("all");
  const [clipId, setClipId] = useState<string | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);

  const totals = useMemo(() => countOutcomes(data.events), [data.events]);
  const openClip = data.events.find((e) => e.event_id === clipId) ?? null;
  const attentionZones = (data.insights?.findings ?? [])
    .filter((f) => f.severity === "act" && f.zone_id)
    .map((f) => f.zone_id as string);

  const ready = data.status !== "loading" || data.events.length > 0;

  const toggleZone = (id: string) => setZoneId((current) => (current === id ? null : id));

  return (
    <div className={styles.shell}>
      <div className={styles.main}>
        <StatusBar data={data} onOpenCopilot={() => setCopilotOpen(true)} />

        {data.status === "error" && data.events.length === 0 ? (
          <section className={styles.offline} aria-live="polite">
            <h1>No data</h1>
            <p>{data.error}</p>
            <p>
              Start the backend from the repository root with{" "}
              <code>uvicorn backend_service.main:app --port 8000</code>. This page retries every 8
              seconds.
            </p>
          </section>
        ) : (
          <main className={styles.content}>
            <ShelfHeadline totals={totals} loading={data.status === "loading"} />

            <div className={styles.hero}>
              <ShelfMap
                ready={ready}
                events={data.events}
                selectedZone={zoneId}
                attentionZones={attentionZones}
                onSelectZone={toggleZone}
              />
              <Findings
                insights={data.insights}
                status={data.insightsStatus}
                events={data.events}
                onOpenClip={setClipId}
                onSelectZone={setZoneId}
              />
            </div>

            {ready && (
              <>
                <ZoneOutcomes
                  events={data.events}
                  selectedZone={zoneId}
                  onSelectZone={toggleZone}
                  onSelectOutcome={setOutcome}
                />

                <ClipLog
                  events={data.events}
                  zoneId={zoneId}
                  outcome={outcome}
                  onClearZone={() => setZoneId(null)}
                  onOutcomeChange={setOutcome}
                  onOpenClip={setClipId}
                />
              </>
            )}
          </main>
        )}
      </div>

      <CopilotPanel
        eventCount={data.events.length}
        quickPrompts={data.quickPrompts}
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        onOpenClip={setClipId}
      />

      <ReplayDialog event={openClip} onClose={() => setClipId(null)} />
    </div>
  );
}
