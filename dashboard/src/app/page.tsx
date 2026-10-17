"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";

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

interface QuickPrompt {
  id: string;
  title: string;
  prompt: string;
  icon: string;
  category: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  referenced_events?: string[];
  suggested_followups?: string[];
}

const DEFAULT_QUICK_PROMPTS: QuickPrompt[] = [
  {
    id: "cereal_abandonment",
    title: "Cereal Shelf Abandonment",
    prompt: "Why are shoppers abandoning items at the cereal shelf, and what behaviors did the AI observe?",
    icon: "📉",
    category: "Conversion & Loss",
  },
  {
    id: "zone_comparison",
    title: "Cereal vs Snacks Comparison",
    prompt: "Compare the conversion rate, average dwell time, and shopper volume between Left Bay Cereal and Right Bay Snacks.",
    icon: "⚖️",
    category: "Merchandising",
  },
  {
    id: "showrooming_behavior",
    title: "Smartphone & Price Checking",
    prompt: "Did any shoppers exhibit smartphone photography, price-checking, or showrooming behaviors at the shelves?",
    icon: "📱",
    category: "Shopper Behavior",
  },
  {
    id: "edge_efficiency",
    title: "Edge Bandwidth & Latency",
    prompt: "What are our edge compute bandwidth savings and cloud analysis latency metrics across the camera nodes?",
    icon: "⚡",
    category: "System Health",
  },
  {
    id: "bottom_shelf_dwell",
    title: "Shelf Height Engagement",
    prompt: "How do shoppers interact with lower vs eye-level shelves, and did crouching or reach behavior impact purchase decisions?",
    icon: "🛒",
    category: "Store Layout",
  },
];

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

  // Copilot Chatbot State
  const [copilotOpen, setCopilotOpen] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [quickPrompts, setQuickPrompts] = useState<QuickPrompt[]>(DEFAULT_QUICK_PROMPTS);
  const [chatInput, setChatInput] = useState<string>("");
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const fetchData = async () => {
    try {
      const [sumRes, evtsRes, promptsRes] = await Promise.all([
        fetch(`${API_BASE}/analytics/summary`),
        fetch(`${API_BASE}/events?limit=50`),
        fetch(`${API_BASE}/chat/quick-prompts`).catch(() => null),
      ]);

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setSummary(sumData);
      }

      if (evtsRes.ok) {
        const evtsData = await evtsRes.json();
        setEvents(evtsData);
      }

      if (promptsRes && promptsRes.ok) {
        const promptData = await promptsRes.json();
        if (Array.isArray(promptData) && promptData.length > 0) {
          setQuickPrompts(promptData);
        }
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

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages, chatLoading]);

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

  // Handle Copilot Question Submission
  const handleSendChat = async (textToSubmit?: string) => {
    const question = (textToSubmit || chatInput).trim();
    if (!question || chatLoading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          history: chatMessages.slice(-6).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: data.response,
          referenced_events: data.referenced_events || [],
          suggested_followups: data.suggested_followups || [],
          timestamp: data.timestamp,
        };
        setChatMessages((prev) => [...prev, assistantMsg]);
      } else {
        throw new Error(`Server returned ${res.status}`);
      }
    } catch (err: any) {
      console.error("Chat error:", err);
      const fallbackMsg: ChatMessage = {
        role: "assistant",
        content: `Sorry, I encountered an issue retrieving the analysis: ${err.message || "Network error"}. Please ensure the backend is running.`,
      };
      setChatMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  // Replay linking from AI Copilot response to video modal
  const handleReplayEvent = async (eventId: string) => {
    const found = events.find((e) => e.event_id === eventId);
    if (found) {
      setSelectedEvent(found);
    } else {
      try {
        const res = await fetch(`${API_BASE}/events/${eventId}`);
        if (res.ok) {
          const evt = await res.json();
          setSelectedEvent(evt);
        }
      } catch (err) {
        console.error("Could not fetch referenced event:", err);
      }
    }
  };

  // Simple, safe Markdown renderer for chat responses
  const renderFormattedContent = (content: string) => {
    const lines = content.split("\n");
    const elements: React.ReactNode[] = [];
    let inList = false;
    let listItems: React.ReactNode[] = [];

    const flushList = () => {
      if (inList && listItems.length > 0) {
        elements.push(<ul key={`ul-${elements.length}`}>{listItems}</ul>);
        listItems = [];
        inList = false;
      }
    };

    const formatInline = (text: string) => {
      const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
      return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={i}
              style={{
                background: "rgba(255,255,255,0.08)",
                padding: "2px 6px",
                borderRadius: "4px",
                fontFamily: "monospace",
                color: "#38bdf8",
              }}
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      });
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) {
        flushList();
        continue;
      }

      if (line.startsWith("### ")) {
        flushList();
        elements.push(<h3 key={`h3-${i}`}>{formatInline(line.slice(4))}</h3>);
      } else if (line.startsWith("#### ")) {
        flushList();
        elements.push(<h4 key={`h4-${i}`}>{formatInline(line.slice(5))}</h4>);
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        inList = true;
        listItems.push(<li key={`li-${i}`}>{formatInline(line.slice(2))}</li>);
      } else {
        flushList();
        elements.push(<p key={`p-${i}`}>{formatInline(line)}</p>);
      }
    }
    flushList();
    return elements;
  };

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
            className="header-copilot-btn"
            id="header-copilot-btn"
            onClick={() => setCopilotOpen(true)}
            title="Open Conversational Store Copilot"
          >
            ✨ Ask AIsle Copilot
          </button>

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
          <div className="kpi-footer">
            <span className="trend-badge positive">Live Tracking</span>
            <span className="footer-subtext">across shelf cameras</span>
          </div>
        </div>

        <div className="kpi-card" id="kpi-conversion" style={{ "--card-accent": "var(--accent-emerald)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Shelf Conversion</span>
            <span className="kpi-icon">🎯</span>
          </div>
          <div className="kpi-value">
            {summary ? `${summary.conversion_rate}%` : "--%"}
          </div>
          <div className="kpi-footer">
            <span className="trend-badge positive">
              {summary ? summary.breakdown_by_outcome.taken || 0 : 0} purchases
            </span>
            <span className="footer-subtext">placed in cart</span>
          </div>
        </div>

        <div className="kpi-card" id="kpi-abandonment" style={{ "--card-accent": "var(--accent-rose)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Cart Abandonment</span>
            <span className="kpi-icon">⚠️</span>
          </div>
          <div className="kpi-value">
            {summary ? `${summary.abandonment_rate}%` : "--%"}
          </div>
          <div className="kpi-footer">
            <span className="trend-badge negative">
              {summary ? summary.breakdown_by_outcome.returned || 0 : 0} returned
            </span>
            <span className="footer-subtext">items put back</span>
          </div>
        </div>

        <div className="kpi-card" id="kpi-dwell" style={{ "--card-accent": "var(--accent-indigo)" } as React.CSSProperties}>
          <div className="kpi-header">
            <span className="kpi-title">Average Dwell</span>
            <span className="kpi-icon">⏱️</span>
          </div>
          <div className="kpi-value">
            {summary ? `${summary.average_dwell_time_seconds}s` : "--s"}
          </div>
          <div className="kpi-footer">
            <span className="trend-badge neutral">Active inspection</span>
            <span className="footer-subtext">per customer visit</span>
          </div>
        </div>
      </section>

      {/* Zone Performance Comparison Matrix */}
      {summary?.zones && summary.zones.length > 0 && (
        <section className="zone-section" id="zone-comparison-section">
          <div className="section-header">
            <div>
              <h2>Retail Shelf Zone Matrix</h2>
              <p>Granular physical performance, conversion efficiency, and dwell correlation by shelf zone</p>
            </div>
            <div className="zone-legend">
              <span className="legend-tag high">High Conversion (&gt;50%)</span>
              <span className="legend-tag med">Average</span>
            </div>
          </div>

          <div className="zone-grid">
            {summary.zones.map((zone) => {
              const isHigh = zone.conversion_rate >= 50;
              return (
                <div className="zone-card" key={zone.zone_id} id={`zone-card-${zone.zone_id}`}>
                  <div className="zone-card-top">
                    <div>
                      <span className="zone-id-tag">{zone.zone_id}</span>
                      <h3 className="zone-name">{zone.display_name}</h3>
                    </div>
                    <span className={`zone-status-badge ${isHigh ? "high" : "med"}`}>
                      {zone.conversion_rate}% Conv
                    </span>
                  </div>

                  <div className="zone-metrics-row">
                    <div className="zone-submetric">
                      <span className="submetric-val">{zone.interactions}</span>
                      <span className="submetric-lbl">Interactions</span>
                    </div>
                    <div className="zone-submetric">
                      <span className="submetric-val">{zone.average_dwell}s</span>
                      <span className="submetric-lbl">Avg Dwell</span>
                    </div>
                    <div className="zone-submetric">
                      <span className="submetric-val" style={{ color: "var(--accent-emerald)" }}>{zone.taken_count}</span>
                      <span className="submetric-lbl">Taken</span>
                    </div>
                    <div className="zone-submetric">
                      <span className="submetric-val" style={{ color: "var(--accent-rose)" }}>{zone.returned_count}</span>
                      <span className="submetric-lbl">Returned</span>
                    </div>
                  </div>

                  <div className="zone-bar-wrapper">
                    <div className="zone-bar-label">
                      <span>Conversion Progress</span>
                      <strong>{zone.conversion_rate}%</strong>
                    </div>
                    <div className="zone-bar-bg">
                      <div
                        className="zone-bar-fill"
                        style={{
                          width: `${Math.min(100, zone.conversion_rate)}%`,
                          background: isHigh
                            ? "linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan))"
                            : "linear-gradient(90deg, var(--accent-amber), var(--accent-rose))",
                        }}
                      />
                    </div>
                  </div>

                  <div className="zone-products-preview">
                    <strong>Sample Categories:</strong>
                    <div className="product-tags">
                      {zone.sample_products.map((p, idx) => (
                        <span key={idx} className="product-tag">{p}</span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Multimodal Interaction Feed */}
      <section className="feed-section" id="interaction-feed-section">
        <div className="feed-header">
          <div>
            <h2>Multimodal Interaction Audit Log</h2>
            <p>Live edge detections verified by Gemini 2.5 Flash with behavioral reasoning and video replays</p>
          </div>

          <div className="filter-group">
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="filter-select"
              id="filter-outcome-select"
            >
              <option value="all">All Outcomes</option>
              <option value="taken">Taken (Converted)</option>
              <option value="returned">Returned (Abandoned)</option>
              <option value="none">None (Browsed)</option>
            </select>

            <select
              value={zoneFilter}
              onChange={(e) => setZoneFilter(e.target.value)}
              className="filter-select"
              id="filter-zone-select"
            >
              <option value="all">All Zones</option>
              {zonesList.map((z) => (
                <option key={z} value={z}>{z}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="event-list" id="event-list-container">
          {filteredEvents.map((evt) => {
            const isTaken = evt.conversion_outcome.toLowerCase() === "taken";
            const isReturned = evt.conversion_outcome.toLowerCase() === "returned";

            let outcomeClass = "outcome-none";
            let outcomeIcon = "👀";
            if (isTaken) {
              outcomeClass = "outcome-taken";
              outcomeIcon = "✅";
            } else if (isReturned) {
              outcomeClass = "outcome-returned";
              outcomeIcon = "↩️";
            }

            return (
              <div className="event-card" key={evt.event_id} id={`event-card-${evt.event_id}`}>
                <div className="event-main">
                  <div className="event-badges">
                    <span className={`outcome-pill ${outcomeClass}`}>
                      {outcomeIcon} {evt.conversion_outcome.toUpperCase()}
                    </span>
                    <span className="type-pill">
                      {evt.interaction_type.toUpperCase()}
                    </span>
                    <span className="zone-pill">
                      📍 {evt.zone_id}
                    </span>
                    <span className="dwell-pill">
                      ⏱️ {evt.zone_dwell_time_seconds}s Dwell
                    </span>
                    {evt.gemini_latency_ms && (
                      <span className="latency-pill" title="Gemini 2.5 Flash Cloud Latency">
                        ⚡ {(evt.gemini_latency_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>

                  <p className="behavioral-narrative">
                    "{evt.behavioral_summary}"
                  </p>

                  <div className="event-meta">
                    <span><strong>Product:</strong> {evt.product_category_engaged || "General"}</span>
                    <span><strong>Demographic:</strong> {evt.estimated_demographic}</span>
                    <span><strong>Shoppers:</strong> {evt.shopper_group_size}</span>
                    <span className="event-time">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>

                <div className="event-actions">
                  <button
                    className="replay-btn"
                    id={`replay-btn-${evt.event_id}`}
                    onClick={() => setSelectedEvent(evt)}
                    title="Watch the exact interaction video slice"
                  >
                    🎬 Replay Clip
                  </button>
                </div>
              </div>
            );
          })}

          {filteredEvents.length === 0 && (
            <div className="empty-state" id="empty-events-state">
              <p style={{ color: "var(--text-muted)" }}>No interaction events match the selected filter.</p>
            </div>
          )}
        </div>
      </section>

      {/* Floating Action Button for Copilot */}
      <button
        className="copilot-fab"
        id="copilot-fab-btn"
        onClick={() => setCopilotOpen(true)}
        title="Chat with AIsle Copilot"
      >
        <span className="copilot-fab-sparkle">✨</span>
        <span>AIsle Copilot</span>
      </button>

      {/* Copilot Drawer Backdrop */}
      {copilotOpen && (
        <div
          className="copilot-backdrop"
          id="copilot-backdrop"
          onClick={() => setCopilotOpen(false)}
        />
      )}

      {/* Copilot Slide-over Drawer */}
      <div
        className={`copilot-drawer ${copilotOpen ? "open" : ""}`}
        id="copilot-drawer-panel"
      >
        <div className="copilot-header">
          <div className="copilot-header-brand">
            <div className="copilot-avatar">✨</div>
            <div className="copilot-title">
              <h2>AIsle Retail Copilot</h2>
              <div className="copilot-subtitle">
                <span className="copilot-status-dot"></span>
                <span>Grounded on 17 Benchmark Store Events • Gemini 2.5</span>
              </div>
            </div>
          </div>
          <div className="copilot-header-actions">
            {chatMessages.length > 0 && (
              <button
                className="copilot-icon-btn"
                onClick={() => setChatMessages([])}
                title="Clear conversation"
              >
                🗑️ Clear
              </button>
            )}
            <button
              className="copilot-icon-btn"
              onClick={() => setCopilotOpen(false)}
              title="Close drawer"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="copilot-body" ref={chatScrollRef}>
          {/* Quick Prompts Section (Shown when conversation is fresh or on demand) */}
          {chatMessages.length === 0 && (
            <div className="quick-prompts-section">
              <div className="quick-prompts-header">
                <h3>⚡ Recommended Store Inquiries</h3>
              </div>
              <div className="quick-prompts-grid">
                {quickPrompts.map((qp) => (
                  <button
                    key={qp.id}
                    className="quick-prompt-card"
                    id={`quick-prompt-${qp.id}`}
                    onClick={() => handleSendChat(qp.prompt)}
                  >
                    <div className="quick-prompt-icon">{qp.icon}</div>
                    <div className="quick-prompt-details">
                      <div className="quick-prompt-top">
                        <span className="quick-prompt-title">{qp.title}</span>
                        <span className="quick-prompt-cat">{qp.category}</span>
                      </div>
                      <p className="quick-prompt-text">"{qp.prompt}"</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat Messages */}
          <div className="chat-messages">
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`chat-row ${msg.role}`}
                id={`chat-msg-${idx}`}
              >
                <div className={`chat-bubble ${msg.role}`}>
                  {msg.role === "assistant"
                    ? renderFormattedContent(msg.content)
                    : <p>{msg.content}</p>}
                </div>

                {/* Referenced Events for 1-Click Video Replay */}
                {msg.role === "assistant" &&
                  msg.referenced_events &&
                  msg.referenced_events.length > 0 && (
                    <div className="chat-referenced-events">
                      <span className="chat-ref-label">
                        🎥 Verified Interactions:
                      </span>
                      {msg.referenced_events.map((evtId) => (
                        <button
                          key={evtId}
                          className="chat-replay-chip"
                          onClick={() => handleReplayEvent(evtId)}
                          title={`Watch interaction replay for ${evtId}`}
                        >
                          🎬 Replay <code>{evtId}</code>
                        </button>
                      ))}
                    </div>
                  )}

                {/* Follow-up Suggestions */}
                {msg.role === "assistant" &&
                  msg.suggested_followups &&
                  msg.suggested_followups.length > 0 && (
                    <div className="chat-followups">
                      <span className="chat-followup-label">
                        Suggested Follow-ups:
                      </span>
                      {msg.suggested_followups.map((f, fIdx) => (
                        <button
                          key={fIdx}
                          className="chat-followup-chip"
                          onClick={() => handleSendChat(f)}
                        >
                          💬 {f}
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            ))}

            {/* Typing Indicator */}
            {chatLoading && (
              <div className="chat-row assistant">
                <div className="chat-typing-bubble">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer Input */}
        <div className="copilot-footer">
          <form
            className="copilot-input-form"
            onSubmit={(e) => {
              e.preventDefault();
              handleSendChat();
            }}
          >
            <input
              type="text"
              className="copilot-input"
              id="copilot-chat-input"
              placeholder="Ask about shelf conversion, dwell time, or showrooming..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={chatLoading}
            />
            <button
              type="submit"
              className="copilot-send-btn"
              id="copilot-send-btn"
              disabled={chatLoading || !chatInput.trim()}
            >
              <span>Send</span>
              <span>➤</span>
            </button>
          </form>
        </div>
      </div>

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
