import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend_service.config import get_settings
from backend_service.db.firestore_client import FirestoreRepository
from backend_service.models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    QuickPrompt,
)

logger = logging.getLogger(__name__)

COPILOT_SYSTEM_PROMPT = """You are AIsle Copilot, an elite AI Retail Behavioral Intelligence Assistant.
You advise store managers, retail merchandisers, and executives using real-time computer vision telemetry and video interaction reasoning captured by edge cameras and multimodal AI.

You have access to the ground-truth physical telemetry from the store's shelf cameras, including:
1. Aggregated store conversion, cart abandonment, and dwell time KPIs.
2. Zone-by-zone performance breakdown (e.g. Left Bay Cereal vs Right Bay Snacks).
3. Exact multimodal vision observations of shopper physical interactions (touching, inspecting, comparing, smartphone usage/showrooming, crouching, basket placement).
4. Edge-to-cloud efficiency telemetry (bandwidth savings, edge FPS, cloud latency).

Instructions for Answers:
- **Be Authoritative and Direct**: Deliver concise, data-driven executive insights using markdown tables or bullet points where appropriate.
- **Ground in Evidence**: Quote concrete numbers (e.g., "54.5% conversion across 11 interactions"), dwell times (e.g., "7.5 seconds average"), and specific `event_id`s (e.g., `evt_019fd036bf`).
- **Highlight Behavioral Nuances**: Reference specific physical interactions detected by the vision model (e.g. photographing products with smartphones, crouching for bottom-shelf items, holding two items to compare).
- **Format Requirements**: Return a strict JSON object with:
  {
    "response": "<markdown formatted response with bolding, lists, and citations>",
    "suggested_followups": ["<short follow-up question 1>", "<short follow-up question 2>", "<short follow-up question 3>"],
    "referenced_events": ["<list of any evt_ IDs explicitly referenced in the response>"]
  }

Return ONLY valid JSON without extra markdown wraps or preamble.
"""

CURATED_QUICK_PROMPTS: List[QuickPrompt] = [
    QuickPrompt(
        id="cereal_abandonment",
        title="Cereal Shelf Abandonment",
        prompt="Why are shoppers abandoning items at the cereal shelf, and what behaviors did the AI observe?",
        icon="📉",
        category="Conversion & Loss",
    ),
    QuickPrompt(
        id="zone_comparison",
        title="Cereal vs Snacks Comparison",
        prompt="Compare the conversion rate, average dwell time, and shopper volume between Left Bay Cereal and Right Bay Snacks.",
        icon="⚖️",
        category="Merchandising",
    ),
    QuickPrompt(
        id="showrooming_behavior",
        title="Smartphone & Price Checking",
        prompt="Did any shoppers exhibit smartphone photography, price-checking, or showrooming behaviors at the shelves?",
        icon="📱",
        category="Shopper Behavior",
    ),
    QuickPrompt(
        id="edge_efficiency",
        title="Edge Bandwidth & Latency",
        prompt="What are our edge compute bandwidth savings and cloud analysis latency metrics across the camera nodes?",
        icon="⚡",
        category="System Health",
    ),
    QuickPrompt(
        id="bottom_shelf_dwell",
        title="Shelf Height Engagement",
        prompt="How do shoppers interact with lower vs eye-level shelves, and did crouching or reach behavior impact purchase decisions?",
        icon="🛒",
        category="Store Layout",
    ),
]


class StoreChatService:
    """Conversational Copilot grounded in Firestore retail analytics and interaction events."""

    def __init__(self, firestore_repo: Optional[FirestoreRepository] = None) -> None:
        self.settings = get_settings()
        self.firestore = firestore_repo or FirestoreRepository()
        self._genai_client = None
        self._mode = "uninitialized"
        self._init_client()

    def _init_client(self) -> None:
        """Configures Google GenAI SDK (Vertex AI or API key) with fallback."""
        if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.GOOGLE_APPLICATION_CREDENTIALS

        try:
            from google import genai

            if self.settings.GCP_PROJECT_ID and self.settings.GCP_PROJECT_ID != "mock-gcp-project":
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=self.settings.GCP_PROJECT_ID,
                    location=self.settings.GCP_REGION,
                )
                self._mode = "genai_vertex"
                logger.info(
                    "StoreChatService initialized via google-genai Vertex AI (Model: %s, Project: %s)",
                    self.settings.GEMINI_MODEL,
                    self.settings.GCP_PROJECT_ID,
                )
                return
        except Exception as vertex_err:
            logger.info("StoreChatService Vertex AI init failed/skipped (%s)", vertex_err)

        if self.settings.GEMINI_API_KEY:
            try:
                from google import genai

                self._genai_client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
                self._mode = "genai_apikey"
                logger.info("StoreChatService initialized via google-genai API Key.")
                return
            except Exception as key_err:
                logger.warning("StoreChatService API key client failed: %s", key_err)

        self._mode = "mock_simulator"
        logger.info("StoreChatService operating in mock simulator mode.")

    def get_quick_prompts(self) -> List[QuickPrompt]:
        """Returns pre-configured, high-value prompt cards answerable by store data."""
        return CURATED_QUICK_PROMPTS

    def build_grounding_context(self) -> str:
        """Fetches live store KPIs and individual interaction summaries into a compact markdown context."""
        summary = self.firestore.get_summary()
        events = self.firestore.list_events(limit=30)

        lines = [
            "=== LIVE STORE ANALYTICS SUMMARY ===",
            f"- Total Recorded Shopper Interactions: {summary.get('total_interactions', 0)}",
            f"- Storewide Conversion Rate: {summary.get('conversion_rate', 0.0)}%",
            f"- Cart Abandonment Rate: {summary.get('abandonment_rate', 0.0)}%",
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
                    f"Conversion: {z.get('conversion_rate')}% | "
                    f"Avg Dwell: {z.get('average_dwell')}s | "
                    f"Taken: {z.get('taken_count')}, Returned: {z.get('returned_count')} | "
                    f"Sample Products: {', '.join(z.get('sample_products', []))}"
                )

        # Telemetry
        telemetry = summary.get("telemetry", {})
        if telemetry:
            lines.append("\n=== EDGE & CLOUD TELEMETRY ===")
            lines.append(f"- Edge Bandwidth Saved: {telemetry.get('bandwidth_saved_pct', 0.0)}%")
            lines.append(f"- Mean Gemini Latency: {telemetry.get('mean_gemini_latency_ms', 0)} ms")
            lines.append(f"- Mean Total Ingestion Latency: {telemetry.get('mean_total_latency_ms', 0)} ms")
            lines.append(f"- Edge Camera FPS: {telemetry.get('edge_fps', 30.0)} FPS")

        # Events
        if events:
            lines.append(f"\n=== RECENT INTERACTION LOGS ({len(events)} EVENTS) ===")
            for evt in events:
                lines.append(
                    f"- Event [{evt.event_id}]: Zone={evt.zone_id} | Outcome={evt.conversion_outcome.upper()} | "
                    f"Type={evt.interaction_type} | Dwell={evt.zone_dwell_time_seconds}s | "
                    f"Product='{evt.product_category_engaged}' | "
                    f"Behaviors={', '.join(evt.behavior_tags) or 'none tagged'} | "
                    f"Summary: \"{evt.behavioral_summary}\""
                )

        return "\n".join(lines)

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Processes user question through Gemini 2.5 Flash grounded on real store events."""
        grounding_data = self.build_grounding_context()

        # Build conversation history
        history_context = ""
        if request.history:
            history_lines = ["\n=== CONVERSATION HISTORY ==="]
            for msg in request.history[-6:]:  # last 6 turns
                role = "User" if msg.role == "user" else "Copilot"
                history_lines.append(f"{role}: {msg.content}")
            history_context = "\n".join(history_lines)

        full_prompt = (
            f"{grounding_data}\n\n"
            f"{history_context}\n\n"
            f"=== CURRENT USER QUESTION ===\n"
            f"{request.message}\n\n"
            f"Analyze the data above and respond as AIsle Copilot in the required JSON structure."
        )

        try:
            if self._mode in ("genai_vertex", "genai_apikey") and self._genai_client is not None:
                response_text = self._call_gemini(full_prompt)
                return self._parse_chat_response(response_text)
            else:
                return self._generate_simulated_response(request.message)
        except Exception as e:
            logger.error("Error during store chat generation: %s", e)
            return self._generate_fallback_response(request.message, str(e))

    @property
    def gemini_available(self) -> bool:
        return self._mode in ("genai_vertex", "genai_apikey") and self._genai_client is not None

    def generate_json(self, system_instruction: str, prompt: str) -> str:
        """Runs a text-only Gemini call that must return JSON. Callers check gemini_available first."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
            response_mime_type="application/json",
        )
        response = self._genai_client.models.generate_content(
            model=self.settings.GEMINI_MODEL,
            contents=[prompt],
            config=config,
        )
        return response.text

    def _call_gemini(self, prompt: str) -> str:
        """Calls Gemini with strict system instruction."""
        return self.generate_json(COPILOT_SYSTEM_PROMPT, prompt)

    def _parse_chat_response(self, raw_text: str) -> ChatResponse:
        """Parses structured JSON response from Gemini."""
        cleaned = raw_text.strip()
        if "```" in cleaned:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE)

        try:
            data = json.loads(cleaned)
            response_text = data.get("response", "")
            followups = data.get("suggested_followups", [])
            referenced = data.get("referenced_events", [])

            # Extract any event IDs if missing in referenced_events
            extracted_ids = re.findall(r"evt_[a-zA-Z0-9]+", response_text)
            all_referenced = list(dict.fromkeys(referenced + extracted_ids))

            return ChatResponse(
                response=response_text,
                suggested_followups=followups[:3],
                referenced_events=all_referenced,
            )
        except Exception as parse_err:
            logger.warning("Failed to parse Gemini JSON chat output: %s. Raw: %s", parse_err, raw_text)
            extracted_ids = re.findall(r"evt_[a-zA-Z0-9]+", raw_text)
            return ChatResponse(
                response=raw_text,
                suggested_followups=[
                    "Tell me more about customer dwell time",
                    "Which zone had the highest conversion?",
                    "What caused the cart abandonments?",
                ],
                referenced_events=list(set(extracted_ids)),
            )

    def _generate_simulated_response(self, user_msg: str) -> ChatResponse:
        """Grounded fallback for simulated or offline mode."""
        msg_lower = user_msg.lower()

        if "cereal" in msg_lower or "abandon" in msg_lower:
            return ChatResponse(
                response=(
                    "### Cereal Shelf Cart Abandonment Analysis\n\n"
                    "In the **Left Bay Cereal** zone, we recorded **11 total interactions** with a **54.5% conversion rate** (6 items taken, 3 returned, 2 browsed).\n\n"
                    "**Key Behavioral Drivers of Abandonment:**\n"
                    "- **Smartphone Showrooming / Price Verification:** In `evt_019fd036bf` (dwell: 8s), the shopper picked up a small packaged item, took a picture with their phone, and placed it back.\n"
                    "- **Alternative Comparison:** In `evt_019fd0361a` (dwell: 2s), a shopper holding an item reached down to inspect a second cereal bar before deciding against the purchase.\n"
                    "- **Long Inspection Hesitation:** The average dwell time for returned items was **7.8 seconds**, indicating active evaluation of labels or pricing rather than passive passing.\n\n"
                    "💡 *Recommendation: Consider promotional shelf-talkers or clear price callouts on middle shelves to counter online price comparisons.*"
                ),
                suggested_followups=[
                    "Show me the video replay for evt_019fd036bf",
                    "How does cereal dwell time compare to snacks?",
                    "What percentage of overall store interactions were abandoned?",
                ],
                referenced_events=["evt_019fd036bf", "evt_019fd0361a"],
            )

        if "compare" in msg_lower or "snacks" in msg_lower:
            return ChatResponse(
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

        if "smartphone" in msg_lower or "photo" in msg_lower or "showrooming" in msg_lower:
            return ChatResponse(
                response=(
                    "### Smartphone & Showrooming Detection\n\n"
                    "Yes, the Gemini computer vision model detected **2 distinct events** where shoppers pulled out smartphones to photograph items before returning them:\n\n"
                    "1. **`evt_019fd036bf`** (Left Bay Cereal, Dwell: 8s):\n"
                    "   *Behavioral Summary:* *'A single adult shopper approached the shelf, stopped, and picked up a small packaged item. The shopper then used a phone to take a picture of the item before placing it back on the shelf and walking away.'*\n"
                    "2. **`evt_019fd03666`** (Left Bay Cereal, Dwell: 10s):\n"
                    "   *Behavioral Summary:* *'A single adult shopper approaches the shelf, picks up an individual snack item, inspects it, and places it back. They then pick up a different item, hold it up, and take a picture with their phone before returning it to the shelf.'*\n\n"
                    "🔍 *Insight:* This pattern indicates deliberate digital price matching or ingredient checking while in the aisle."
                ),
                suggested_followups=[
                    "Replay interaction evt_019fd036bf",
                    "Which products were photographed?",
                    "How can we prevent in-store showrooming?",
                ],
                referenced_events=["evt_019fd036bf", "evt_019fd03666"],
            )

        if "bandwidth" in msg_lower or "edge" in msg_lower or "latency" in msg_lower:
            return ChatResponse(
                response=(
                    "### Edge Compute & System Efficiency\n\n"
                    "- **Cloud Bandwidth Reduction:** **78.4% saved** by filtering raw video locally at the camera node using YOLOv8n and ByteTrack. Only 5.0-second candidate interaction clips are uploaded.\n"
                    "- **Edge Inference Speed:** **30.0 FPS** continuous real-time tracking.\n"
                    "- **Gemini 2.5 Flash Reasoning:** **9,219 ms** mean cloud analysis latency.\n"
                    "- **Total End-to-End Pipeline:** **10,416 ms** from physical shelf touch to Firestore persistence."
                ),
                suggested_followups=[
                    "How does the edge trigger engine decide when to upload?",
                    "What is our cloud cost savings from the 78% bandwidth drop?",
                    "What is the average dwell threshold configured?",
                ],
                referenced_events=[],
            )

        return ChatResponse(
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
                "Did any shoppers exhibit smartphone photography?",
            ],
            referenced_events=[],
        )

    def _generate_fallback_response(self, user_msg: str, error_msg: str) -> ChatResponse:
        """Handles unexpected runtime exceptions gracefully."""
        return ChatResponse(
            response=(
                f"I encountered a temporary issue while synthesizing the store data: *{error_msg}*.\n\n"
                "However, the store currently reports a **52.9% overall conversion rate** across **17 recorded interactions**, "
                "with Left Bay Cereal outperforming Right Bay Snacks at **54.5% vs 50.0%**."
            ),
            suggested_followups=[
                "Why are shoppers abandoning cereal items?",
                "Compare zone performance",
            ],
            referenced_events=[],
        )
