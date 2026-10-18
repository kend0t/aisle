import logging
import re
from typing import List

from backend_service.db.firestore_client import EventRepository, summarize
from backend_service.models.chat import ChatRequest, ChatResponse, CopilotReply, QuickPrompt
from backend_service.models.interaction_event import InteractionEvent
from backend_service.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

COPILOT_SYSTEM_PROMPT = """You are AIsle Copilot, an elite AI Retail Behavioral Intelligence Assistant.
You advise store managers, retail merchandisers, and executives using real-time computer vision telemetry and video interaction reasoning captured by edge cameras and multimodal AI.

You have access to the ground-truth physical telemetry from the store's shelf cameras, including:
1. Aggregated store conversion, cart abandonment, and dwell time KPIs.
2. Zone-by-zone performance breakdown (e.g. Left Bay Cereal vs Right Bay Snacks).
3. Exact multimodal vision observations of shopper physical interactions (touching, inspecting, comparing, crouching, basket placement, hesitating).
4. Measured cloud latency for the Gemini clip analysis.

Instructions for Answers:
- **Be Short and Direct**: Answer in about 80 words or fewer. Use a markdown table only when comparing; otherwise use short bullet points or one paragraph.
- **Use the store's terms**: Say "taken rate" (not conversion) and "put-back rate" (not cart abandonment). An item is "put back", not "abandoned".
- **Plain behavior names**: Write behaviors in plain words ("compared items", "read nutrition labels", "crouched for lower shelf"), never as raw tag names.
- **Ground in Evidence**: Quote concrete numbers (e.g., "54.5% conversion across 11 interactions"), dwell times (e.g., "7.5 seconds average"), and specific `event_id`s (e.g., `evt_019fd036bf`).
- **Highlight Behavioral Nuances**: Reference specific physical interactions detected by the vision model (e.g. reading nutrition panels, crouching for bottom-shelf items, holding two items to compare, pausing with hesitation).
- **Fields**: `response` is the markdown answer, `suggested_followups` holds up to 3 short questions, and `referenced_events` lists every evt_ ID the answer cites.
"""

CURATED_QUICK_PROMPTS: List[QuickPrompt] = [
    # The dashboard shows the first three as starter chips.
    QuickPrompt(
        id="putback_behaviors",
        title="What comes before a put-back",
        prompt="Which behaviors did shoppers show before putting an item back, and what could change at the shelf?",
        icon="↩️",
        category="Conversion & Loss",
    ),
    QuickPrompt(
        id="zone_comparison",
        title="Cereal bay against snack bay",
        prompt="Compare the cereal bay and the snack bay: clips, taken rate, put-back rate, and time at shelf.",
        icon="⚖️",
        category="Merchandising",
    ),
    QuickPrompt(
        id="multi_item_takes",
        title="Multi-item & consecutive takes",
        prompt="Did any shoppers take multiple items consecutively, and what was the total units taken?",
        icon="🛍️",
        category="Merchandising",
    ),
    QuickPrompt(
        id="hesitation_behavior",
        title="Shelf hesitation & put-backs",
        prompt="Which shoppers hesitated before deciding, and what did they do after?",
        icon="⏱️",
        category="Shopper Behavior",
    ),
    QuickPrompt(
        id="cereal_abandonment",
        title="Cereal put-backs",
        prompt="Why are shoppers putting items back at the cereal bay, and what did they do before putting them back?",
        icon="📉",
        category="Conversion & Loss",
    ),
    QuickPrompt(
        id="bottom_shelf_dwell",
        title="Low shelves",
        prompt="Did shoppers who reached for low shelves take the item more or less often than others?",
        icon="🛒",
        category="Store Layout",
    ),
]


EVENT_ID_PATTERN = re.compile(r"evt_[a-zA-Z0-9]+")
MAX_GROUNDING_EVENTS = 50


class StoreChatService:
    """Conversational Copilot grounded in stored retail analytics and interaction events."""

    def __init__(self, repo: EventRepository, gemini: GeminiClient) -> None:
        self.repo = repo
        self.gemini = gemini

    def build_grounding_context(self, events: List[InteractionEvent]) -> str:
        """Store KPIs and per-clip summaries as a compact markdown context."""
        summary = summarize(events)

        total_units = sum(
            e.items_taken_count if e.items_taken_count > 0 else (1 if e.conversion_outcome.value == "taken" else 0)
            for e in events
        )
        lines = [
            "=== LIVE STORE ANALYTICS SUMMARY ===",
            f"- Total Recorded Shopper Interactions: {summary.get('total_interactions', 0)}",
            f"- Total Product Units Taken/Purchased: {total_units} units",
            f"- Taken Rate (clips ending with the item taken / all clips): {summary.get('conversion_rate', 0.0)}%",
            f"- Put-back Rate (items put back / items picked up): {summary.get('abandonment_rate', 0.0)}%",
            f"- Storewide Average Dwell Time: {summary.get('average_dwell_time_seconds', 0.0)} seconds",
            f"- Conversion Breakdown: Taken={summary.get('breakdown_by_outcome', {}).get('taken', 0)}, "
            f"Returned={summary.get('breakdown_by_outcome', {}).get('returned', 0)}, "
            f"None/Browsed={summary.get('breakdown_by_outcome', {}).get('none', 0)}",
            f"- Interaction Type Breakdown: {summary.get('breakdown_by_type', {})}",
        ]

        # Zones
        zones = summary.get("zones", [])
        if zones:
            lines.append("\n=== ZONE PERFORMANCE BREAKDOWN ===")
            for z in zones:
                lines.append(
                    f"- Zone '{z.get('zone_id')}' ({z.get('display_name')}): "
                    f"{z.get('interactions')} interactions | "
                    f"Taken rate: {z.get('conversion_rate')}% | "
                    f"Avg Dwell: {z.get('average_dwell')}s | "
                    f"Taken: {z.get('taken_count')}, Returned: {z.get('returned_count')} | "
                    f"Sample Products: {', '.join(z.get('sample_products', []))}"
                )

        # Telemetry: only the measured Gemini latency.
        gemini_latency = summary.get("telemetry", {}).get("mean_gemini_latency_ms")
        if gemini_latency is not None:
            lines.append("\n=== CLOUD TELEMETRY ===")
            lines.append(f"- Mean Gemini Latency: {gemini_latency} ms")

        # Events
        if events:
            shown = events[:MAX_GROUNDING_EVENTS]
            lines.append(f"\n=== RECENT INTERACTION LOGS ({len(shown)} EVENTS) ===")
            for evt in shown:
                lines.append(
                    f"- Event [{evt.event_id}]: Zone={evt.zone_id} | Outcome={evt.conversion_outcome.upper()} | "
                    f"UnitsTaken={evt.items_taken_count} | "
                    f"Type={evt.interaction_type} | Dwell={evt.zone_dwell_time_seconds}s | "
                    f"Product='{evt.product_category_engaged}' | "
                    f"Behaviors={', '.join(evt.behavior_tags) or 'none tagged'} | "
                    f"Summary: \"{evt.behavioral_summary}\""
                )

        return "\n".join(lines)

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Answers from the stored events. Raises GeminiError when Gemini fails.

        Citations are limited to stored events, so every replay link in the UI works.
        """
        events = self.repo.list_events(limit=500)

        if self.gemini.available:
            history = "\n".join(
                f"{'User' if m.role == 'user' else 'Copilot'}: {m.content}" for m in request.history[-6:]
            )
            prompt = (
                f"{self.build_grounding_context(events)}\n\n"
                + (f"=== CONVERSATION HISTORY ===\n{history}\n\n" if history else "")
                + f"=== CURRENT USER QUESTION ===\n{request.message}"
            )
            reply = self.gemini.generate(
                system=COPILOT_SYSTEM_PROMPT, contents=[prompt], schema=CopilotReply, temperature=0.3
            )
        else:
            reply = self._generate_simulated_response(request.message)

        known_ids = {e.event_id for e in events}
        cited = dict.fromkeys(reply.referenced_events + EVENT_ID_PATTERN.findall(reply.response))
        return ChatResponse(
            response=reply.response,
            suggested_followups=reply.suggested_followups[:3],
            referenced_events=[event_id for event_id in cited if event_id in known_ids],
        )

    def _generate_simulated_response(self, user_msg: str) -> CopilotReply:
        """Canned answers for mock mode, when no Gemini credentials are configured."""
        msg_lower = user_msg.lower()

        if "cereal" in msg_lower or "abandon" in msg_lower:
            return CopilotReply(
                response=(
                    "### Cereal Shelf Cart Abandonment Analysis\n\n"
                    "In the **Left Bay Cereal** zone, we recorded **11 total interactions** with a **54.5% conversion rate** (6 items taken, 3 returned, 2 browsed).\n\n"
                    "**Key Behavioral Drivers of Abandonment:**\n"
                    "- **Detailed Label Inspection:** In `evt_019fd036bf` (dwell: 8s), the shopper picked up a small packaged item, closely inspected the nutrition label, and placed it back.\n"
                    "- **Alternative Comparison:** In `evt_019fd0361a` (dwell: 2s), a shopper holding an item reached down to inspect a second cereal bar before deciding against the purchase.\n"
                    "- **Long Inspection Hesitation:** The average dwell time for returned items was **7.8 seconds**, indicating active evaluation of labels or pricing rather than passive passing.\n\n"
                    "💡 *Recommendation: Consider promotional shelf-talkers or clear price callouts on middle shelves to counter hesitation.*"
                ),
                suggested_followups=[
                    "Show me the video replay for evt_019fd036bf",
                    "How does cereal dwell time compare to snacks?",
                    "What percentage of overall store interactions were abandoned?",
                ],
                referenced_events=["evt_019fd036bf", "evt_019fd0361a"],
            )

        if "compare" in msg_lower or "snacks" in msg_lower:
            return CopilotReply(
                response=(
                    "### Zone Comparison: Left Bay Cereal vs. Right Bay Snacks\n\n"
                    "| Metric | Left Bay Cereal | Right Bay Snacks | Variance |\n"
                    "| :--- | :--- | :--- | :--- |\n"
                    "| **Total Interactions** | 11 | 6 | +83.3% in Cereal |\n"
                    "| **Conversion Rate** | **54.5%** (6 taken) | **50.0%** (3 taken) | +4.5% in Cereal |\n"
                    "| **Abandonment Rate** | 33.3% (3 returned) | 40.0% (2 returned) | Snacks +6.7% abandonment |\n"
                    "| **Average Dwell** | **7.5s** | **6.2s** | +1.3s in Cereal |\n\n"
                    "**Key Takeaways:**\n"
                    "- **Left Bay Cereal** attracts nearly double the shopper traffic and holds customer attention longer (7.5s avg dwell).\n"
                    "- **Right Bay Snacks** experiences faster decision cycles (6.2s) but higher abandonment on packaged snack bars."
                ),
                suggested_followups=[
                    "Why is Right Bay Snacks abandonment higher?",
                    "What are the top products taken in Cereal?",
                    "What was the total edge bandwidth saved for both bays?",
                ],
                referenced_events=["evt_019fd03734", "evt_019fd036bf"],
            )

        if "multi" in msg_lower or "consecutive" in msg_lower or "unit" in msg_lower:
            return CopilotReply(
                response=(
                    "### Multi-Item & Consecutive Pick Analysis\n\n"
                    "Across all recorded interactions, shoppers purchased a total of **10 physical units** across 9 converted visits (average **1.11 units per taken interaction**):\n\n"
                    "- **Right Bay Snacks** demonstrated consecutive selection: in `evt_45a2a242d7` (dwell: 6s) and `evt_019fd03734` (dwell: 7s), shoppers evaluated an initial item before consecutively picking up and purchasing another.\n"
                    "- **Left Bay Cereal** averaged 1.0 units per conversion, characterized by focused nutritional label inspection before deciding.\n\n"
                    "💡 *Merchandising Insight: Snack bays encourage consecutive impulse grabs, making them prime candidates for multi-buy promotions.*"
                ),
                suggested_followups=[
                    "Which products were taken together in snacks?",
                    "What is the average dwell time for multi-item takes?",
                    "Compare total units taken between bays",
                ],
                referenced_events=["evt_45a2a242d7", "evt_019fd03734"],
            )

        if "hesitat" in msg_lower or "label" in msg_lower or "inspect" in msg_lower:
            return CopilotReply(
                response=(
                    "### Shelf Hesitation & Label Inspection Analysis\n\n"
                    "The Gemini computer vision model detected **2 distinct events** where shoppers engaged in extended inspection or hesitation before returning items:\n\n"
                    "1. **`evt_019fd036bf`** (Left Bay Cereal, Dwell: 8s):\n"
                    "   *Behavioral Summary:* *'A single adult shopper approached the shelf, stopped, and picked up a small packaged item. The shopper turned the package to inspect the label before placing it back on the shelf and walking away.'*\n"
                    "2. **`evt_019fd03666`** (Left Bay Cereal, Dwell: 10s):\n"
                    "   *Behavioral Summary:* *'A single adult shopper approaches the shelf, picks up an individual snack item, inspects it, and places it back. They then pick up a different item, hold it up to read ingredients, and hesitate before returning it to the shelf.'*\n\n"
                    "🔍 *Insight:* This pattern indicates deliberate label evaluation and ingredient checking rather than impulse abandonment."
                ),
                suggested_followups=[
                    "Replay interaction evt_019fd036bf",
                    "Which products had the highest hesitation rate?",
                    "How can we improve label clarity on the shelf?",
                ],
                referenced_events=["evt_019fd036bf", "evt_019fd03666"],
            )

        if "bandwidth" in msg_lower or "edge" in msg_lower or "latency" in msg_lower:
            return CopilotReply(
                response=(
                    "### Edge Compute & System Efficiency\n\n"
                    "- **Cloud Bandwidth Reduction:** **78.4% saved** by filtering raw video locally at the camera node using YOLOv8n and ByteTrack. Only 5.0-second candidate interaction clips are uploaded.\n"
                    "- **Edge Inference Speed:** **30.0 FPS** continuous real-time tracking.\n"
                    "- **Gemini 3.8 Flash Reasoning:** **9,219 ms** mean cloud analysis latency.\n"
                    "- **Total End-to-End Pipeline:** **10,416 ms** from physical shelf touch to Firestore persistence."
                ),
                suggested_followups=[
                    "How does the edge trigger engine decide when to upload?",
                    "What is our cloud cost savings from the 78% bandwidth drop?",
                    "What is the average dwell threshold configured?",
                ],
                referenced_events=[],
            )

        return CopilotReply(
            response=(
                f"### Store Behavioral Summary\n\n"
                f"We have captured **17 benchmark shopper interactions** across two primary shelf zones.\n\n"
                f"- **Overall Conversion Rate:** **52.9%** (9 purchases/taken, 5 abandoned/returned, 3 passed/none).\n"
                f"- **Average Dwell Time:** **7.0 seconds** per shelf interaction.\n"
                f"- **Most Active Zone:** **Left Bay Cereal** (11 interactions, 54.5% conversion).\n\n"
                f"How can I assist you further with zone optimization, cart abandonment analysis, or product performance?"
            ),
            suggested_followups=[
                "Why are shoppers abandoning items at the cereal shelf?",
                "Compare Left Bay Cereal vs Right Bay Snacks",
                "Which shoppers hesitated before putting items back?",
            ],
            referenced_events=[],
        )
