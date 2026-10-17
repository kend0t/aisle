"use client";

import React, { useEffect, useState, useMemo } from "react";

interface Telemetry {
  mean_gemini_latency_ms: number;
  mean_total_latency_ms: number;
  bandwidth_saved_pct: number;
  edge_fps: number;
}

interface ZoneStat {
  zone_id: string;
  display_name: string;
  interactions: number;
  conversion_rate: number;
  average_dwell: number;
  taken_count: number;
  returned_count: number;
  sample_products: string[];
}

interface AnalyticsSummary {
  total_interactions: number;
  conversion_rate: number;
  abandonment_rate: number;
  average_dwell_time_seconds: number;
  breakdown_by_outcome: Record<string, number>;
  breakdown_by_type: Record<string, number>;
  breakdown_by_demographic: Record<string, number>;
  zones: ZoneStat[];
  telemetry: Telemetry;
}

interface InteractionEvent {
  event_id: string;
  timestamp: string;
  zone_id: string;
  zone_dwell_time_seconds: number;
  interaction_type: string;
  conversion_outcome: string;
  product_category_engaged: string;
  shopper_group_size: number;
  estimated_demographic: string;
  behavioral_summary: string;
  video_uri?: string;
  gemini_latency_ms?: number;
  total_latency_ms?: number;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export default function DashboardPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [events, setEvents] = useState<InteractionEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<InteractionEvent | null>(null);
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");
  const [zoneFilter, setZoneFilter] = useState<string>("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const fetchData = async () => {
    try {
      const [sumRes, evtsRes] = await Promise.all([
        fetch(`${API_BASE}/analytics/summary`),
        fetch(`${API_BASE}/events?limit=50`),
      ]);

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setSummary(sumData);
      }

      if (evtsRes.ok) {
        const evtsData = await evtsRes.json();
        setEvents(evtsData);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard metrics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const outcomeMatch =
        outcomeFilter === "all" ||
        e.conversion_outcome.toLowerCase() === outcomeFilter.toLowerCase();
      const zoneMatch =
        zoneFilter === "all" || e.zone_id === zoneFilter;
      return outcomeMatch && zoneMatch;
    });
  }, [events, outcomeFilter, zoneFilter]);

  const zonesList = useMemo(() => {
    return Array.from(new Set(events.map((e) => e.zone_id)));
  }, [events]);

  return (
    <main className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="brand-section">
          <div className="brand-logo" id="dashboard-brand-logo">🛒</div>
          <div className="brand-title">
            <h1 id="dashboard-title">AIsle Intelligence</h1>
            <p>Physical Retail Behavioral Understanding & Edge Analytics</p>
          </div>
        </div>

        <div className="header-actions">
          {summary?.telemetry && (
            <div className="telemetry-pill" id="telemetry-pill" title="Live edge & cloud reasoning telemetry">
              <span className="pulse-dot"></span>
              <div className="telemetry-item">
                <span>Edge:</span>
                <strong>{summary.telemetry.edge_fps || 30} FPS</strong>
              </div>
              <span style={{ color: "var(--border-subtle)" }}>|</span>
              <div className="telemetry-item">
                <span>Gemini Vision:</span>
                <strong>{(summary.telemetry.mean_gemini_latency_ms / 1000).toFixed(1)}s</strong>
              </div>
              <span style={{ color: "var(--border-subtle)" }}>|</span>
              <div className="telemetry-item">
                <span>Cloud Egress Saved:</span>
                <strong style={{ color: "var(--accent-emerald)" }}>{summary.telemetry.bandwidth_saved_pct}%</strong>
              </div>
            </div>
          )}

          <button
            className="refresh-btn"
            id="refresh-btn"
            onClick={fetchData}
            title="Refresh metrics from Cloud Firestore"
          >
            ↻ {loading ? "Updating..." : "Refresh"}
          </button>
        </div>
      </header>

      {/* KPI Cards Grid */}
      <section className="kpi-grid">
        <div className="kpi-card" id="kpi-interactions" style={{ "--card-accent": "var(--accent-cyan)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Shopper Visits</span>
            <span className="kpi-icon">👥</span>
          </div>
          <div className="kpi-value">
            {summary ? summary.total_interactions : "--"}
          </div>
          <div className="kpi-subtext">Monitored dwell interactions captured at shelf</div>
        </div>

        <div className="kpi-card" id="kpi-conversion" style={{ "--card-accent": "var(--accent-emerald)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Shelf Conversion Rate</span>
            <span className="kpi-icon">🎯</span>
          </div>
          <div className="kpi-value">
            {summary ? summary.conversion_rate : "--"}
            <span className="kpi-unit">%</span>
          </div>
          <div className="kpi-subtext">
            {summary ? `${summary.breakdown_by_outcome?.taken || 0} product purchases / basket additions` : ""}
          </div>
        </div>

        <div className="kpi-card" id="kpi-abandonment" style={{ "--card-accent": "var(--accent-amber)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Cart Abandonment Rate</span>
            <span className="kpi-icon">↩️</span>
          </div>
          <div className="kpi-value">
            {summary ? summary.abandonment_rate : "--"}
            <span className="kpi-unit">%</span>
          </div>
          <div className="kpi-subtext">
            {summary ? `${summary.breakdown_by_outcome?.returned || 0} items examined & returned to shelf` : ""}
          </div>
        </div>

        <div className="kpi-card" id="kpi-dwell" style={{ "--card-accent": "var(--accent-indigo)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Mean Shelf Dwell</span>
            <span className="kpi-icon">⏱️</span>
          </div>
          <div className="kpi-value">
            {summary ? summary.average_dwell_time_seconds : "--"}
            <span className="kpi-unit">s</span>
          </div>
          <div className="kpi-subtext">Average customer visual & physical evaluation duration</div>
        </div>
      </section>

      {/* Zone Intelligence & Comparison Matrix */}
      <section style={{ marginBottom: "36px" }}>
        <div className="section-header">
          <h2 className="section-title">
            <span>📍</span> Zone Performance Comparison
          </h2>
          <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            Comparing shopper conversion & dwell across monitored bays
          </span>
        </div>

        <div className="zones-grid" id="zones-grid">
          {summary?.zones && summary.zones.length > 0 ? (
            summary.zones.map((zone) => (
              <div className="zone-card" key={zone.zone_id} id={`zone-card-${zone.zone_id}`}>
                <div className="zone-header">
                  <div className="zone-name">{zone.display_name}</div>
                  <span className="zone-badge">
                    {zone.interactions} visits
                  </span>
                </div>

                <div className="zone-stats-row">
                  <div className="zone-stat-box">
                    <div className="zone-stat-value" style={{ color: "var(--accent-emerald)" }}>
                      {zone.conversion_rate}%
                    </div>
                    <div className="zone-stat-label">Conversion</div>
                  </div>
                  <div className="zone-stat-box">
                    <div className="zone-stat-value">
                      {zone.average_dwell}s
                    </div>
                    <div className="zone-stat-label">Avg Dwell</div>
                  </div>
                  <div className="zone-stat-box">
                    <div className="zone-stat-value" style={{ color: "var(--accent-amber)" }}>
                      {zone.returned_count}
                    </div>
                    <div className="zone-stat-label">Returns</div>
                  </div>
                </div>

                <div className="zone-progress-bar" title={`Taken: ${zone.taken_count} | Returns: ${zone.returned_count}`}>
                  <div
                    className="progress-taken"
                    style={{ width: `${zone.conversion_rate}%` }}
                  />
                  <div
                    className="progress-returned"
                    style={{
                      width: `${(zone.returned_count / Math.max(1, zone.interactions)) * 100}%`,
                    }}
                  />
                  <div className="progress-none" style={{ flex: 1 }} />
                </div>

                {zone.sample_products && zone.sample_products.length > 0 && (
                  <div className="zone-products">
                    <strong>Top Products:</strong> {zone.sample_products.join(", ")}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="zone-card" style={{ gridColumn: "1 / -1", textAlign: "center", padding: "40px" }}>
              <p style={{ color: "var(--text-muted)" }}>No zone analytics loaded yet.</p>
            </div>
          )}
        </div>
      </section>

      {/* Behavioral Event Feed & Audit Log */}
      <section>
        <div className="section-header">
          <h2 className="section-title">
            <span>⚡</span> Live Multimodal Event Stream
          </h2>

          <div className="feed-filter-bar" id="feed-filters">
            {["all", "taken", "returned", "none"].map((opt) => (
              <button
                key={opt}
                className={`filter-btn ${outcomeFilter === opt ? "active" : ""}`}
                id={`filter-${opt}`}
                onClick={() => setOutcomeFilter(opt)}
              >
                {opt.toUpperCase()} {opt === "all" ? `(${events.length})` : ""}
              </button>
            ))}

            <select
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-secondary)",
                padding: "6px 12px",
                borderRadius: "var(--radius-full)",
                fontSize: "12px",
                marginLeft: "8px",
              }}
              value={zoneFilter}
              onChange={(e) => setZoneFilter(e.target.value)}
              id="zone-filter-select"
            >
              <option value="all">All Zones</option>
              {zonesList.map((z) => (
                <option key={z} value={z}>
                  {z.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="events-list" id="events-list">
          {filteredEvents.length > 0 ? (
            filteredEvents.map((evt) => {
              const outcomeLower = evt.conversion_outcome.toLowerCase();
              return (
                <div className="event-card" key={evt.event_id} id={`event-${evt.event_id}`}>
                  <div className="event-meta">
                    <span className="event-id">{evt.event_id}</span>
                    <span className="event-time">
                      {new Date(evt.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      ⏱️ {evt.zone_dwell_time_seconds}s dwell
                    </span>
                  </div>

                  <div>
                    <span className={`outcome-badge outcome-${outcomeLower}`} id={`badge-${evt.event_id}`}>
                      {outcomeLower === "taken" && "🛒"}
                      {outcomeLower === "returned" && "↩️"}
                      {outcomeLower === "none" && "👀"}
                      {evt.conversion_outcome}
                    </span>
                    <div className="event-tags">
                      <span className="tag-pill">{evt.zone_id.replace("_", " ")}</span>
                      <span className="tag-pill">{evt.estimated_demographic}</span>
                    </div>
                  </div>

                  <div>
                    <p className="event-narrative">"{evt.behavioral_summary}"</p>
                    <div style={{ marginTop: "4px", fontSize: "12px", color: "var(--text-muted)" }}>
                      🏷️ <strong>Product:</strong> {evt.product_category_engaged || "Shelf item"}
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button
                      className="btn-play-clip"
                      id={`play-btn-${evt.event_id}`}
                      onClick={() => setSelectedEvent(evt)}
                    >
                      ▶ Replay Clip
                    </button>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="event-card" style={{ gridTemplateColumns: "1fr", textAlign: "center", padding: "40px" }}>
              <p style={{ color: "var(--text-muted)" }}>No interaction events match the selected filter.</p>
            </div>
          )}
        </div>
      </section>

      {/* Video Replay Modal */}
      {selectedEvent && (
        <div className="modal-overlay" id="video-modal-overlay" onClick={() => setSelectedEvent(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                🎬 Interaction Replay: <code>{selectedEvent.event_id}</code>
              </h3>
              <button
                className="modal-close-btn"
                id="modal-close-btn"
                onClick={() => setSelectedEvent(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-video-wrapper">
              <video
                className="modal-video"
                id="modal-video-player"
                controls
                autoPlay
                src={`${API_BASE}/events/${selectedEvent.event_id}/stream`}
              >
                Your browser does not support the video tag.
              </video>
            </div>

            <div className="modal-body">
              <p className="modal-narrative">
                <strong>AI Behavioral Reasoning:</strong>
                <br />
                "{selectedEvent.behavioral_summary}"
              </p>

              <div className="modal-meta-row">
                <div>
                  <strong>Outcome:</strong> {selectedEvent.conversion_outcome.toUpperCase()}
                </div>
                <div>
                  <strong>Zone:</strong> {selectedEvent.zone_id}
                </div>
                <div>
                  <strong>Dwell Time:</strong> {selectedEvent.zone_dwell_time_seconds}s
                </div>
                <div>
                  <strong>Product:</strong> {selectedEvent.product_category_engaged}
                </div>
                {selectedEvent.gemini_latency_ms && (
                  <div>
                    <strong>Gemini Latency:</strong> {(selectedEvent.gemini_latency_ms / 1000).toFixed(1)}s
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
