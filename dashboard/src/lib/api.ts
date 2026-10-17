// Types mirror the Pydantic models in backend_service/models/.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export type Outcome = "taken" | "returned" | "none";
export type InteractionType = "passed_by" | "browsed" | "examined" | "compared";
export type BehaviorTag =
  | "phone_check"
  | "compared_alternatives"
  | "low_shelf_reach"
  | "label_inspection"
  | "carried_basket"
  | "hesitated";

export interface InteractionEvent {
  event_id: string;
  timestamp: string;
  zone_id: string;
  zone_dwell_time_seconds: number;
  interaction_type: InteractionType;
  conversion_outcome: Outcome;
  product_category_engaged: string;
  shopper_group_size: number;
  estimated_demographic: string;
  behavioral_summary: string;
  behavior_tags: BehaviorTag[];
  video_uri?: string | null;
  confidence_score?: number | null;
  gemini_latency_ms?: number | null;
  total_latency_ms?: number | null;
  created_at: string;
}

export interface ZoneStat {
  zone_id: string;
  display_name: string;
  interactions: number;
  conversion_rate: number;
  average_dwell: number;
  taken_count: number;
  returned_count: number;
  sample_products: string[];
}

export interface AnalyticsSummary {
  total_interactions: number;
  conversion_rate: number;
  abandonment_rate: number;
  average_dwell_time_seconds: number;
  breakdown_by_outcome: Partial<Record<Outcome, number>>;
  breakdown_by_type: Partial<Record<InteractionType, number>>;
  zones?: ZoneStat[];
}

export type FindingSeverity = "act" | "watch" | "info";

export interface Finding {
  title: string;
  /** Shelf-level change to try. Empty on findings cached before the field existed. */
  action: string;
  detail: string;
  zone_id: string | null;
  severity: FindingSeverity;
  evidence_event_ids: string[];
}

export interface InsightsResponse {
  findings: Finding[];
  source: "gemini" | "rules";
  event_count: number;
  generated_at: string;
}

export interface QuickPrompt {
  id: string;
  title: string;
  prompt: string;
  icon: string;
  category: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  response: string;
  suggested_followups: string[];
  referenced_events: string[];
  timestamp: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(`The backend at ${API_BASE} is not reachable.`);
  }
  if (!res.ok) {
    throw new ApiError(`The backend returned ${res.status} for ${path}.`, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  summary: () => request<AnalyticsSummary>("/analytics/summary"),
  events: () => request<InteractionEvent[]>("/events?limit=500"),
  event: (id: string) => request<InteractionEvent>(`/events/${id}`),
  insights: () => request<InsightsResponse>("/insights"),
  quickPrompts: () => request<QuickPrompt[]>("/chat/quick-prompts"),
  chat: (message: string, history: ChatTurn[]) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    }),
};

export const clipUrl = (id: string) => `${API_BASE}/events/${id}/stream`;
export const thumbnailUrl = (id: string) => `${API_BASE}/events/${id}/thumbnail`;
