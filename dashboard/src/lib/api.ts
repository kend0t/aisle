// Types come from the backend's OpenAPI schema. Regenerate with `npm run gen:api`.
import type { components } from "./api.gen";

type Schemas = components["schemas"];

export type InteractionEvent = Schemas["InteractionEvent"];
export type Outcome = Schemas["ConversionOutcome"];
export type BehaviorTag = Schemas["BehaviorTag"];
export type Finding = Schemas["Finding"];
export type FindingSeverity = Schemas["FindingSeverity"];
export type InsightsResponse = Schemas["InsightsResponse"];
export type QuickPrompt = Schemas["QuickPrompt"];
export type ChatResponse = Schemas["ChatResponse"];
export type ChatTurn = Pick<Schemas["ChatMessage"], "role" | "content">;

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    /** HTTP status; undefined when the backend did not answer at all. */
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
    // FastAPI errors carry a short reason in `detail`, for example "Firestore query failed (NotFound)".
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `The backend returned ${res.status}.`;
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  events: () => request<InteractionEvent[]>("/events?limit=500"),
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
