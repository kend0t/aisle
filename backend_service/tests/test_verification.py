from backend_service.config import get_settings
from backend_service.db.firestore_client import build_repository
from backend_service.models.chat import ChatRequest
from backend_service.models.interaction_event import BehaviorTag, ClipAnalysis, ConversionOutcome
from backend_service.services.chat_service import StoreChatService
from backend_service.services.clip_verification import combine, consistency_issues
from backend_service.services.copilot_tools import CopilotTools


def read(outcome: str, picked: bool, kept: bool, tags=(), dwell: int = 7) -> ClipAnalysis:
    return ClipAnalysis(
        behavioral_summary="A shopper at the shelf.",
        behavior_tags=list(tags),
        picked_up_item=picked,
        left_with_item=kept,
        interaction_type="examined",
        conversion_outcome=outcome,
        zone_dwell_time_seconds=dwell,
        product_category_engaged="cereal",
        shopper_group_size=1,
        estimated_demographic="adult",
    )


def test_unanimous_reads_need_no_review():
    consensus = combine([read("taken", True, True)] * 3)
    assert consensus.analysis.conversion_outcome == ConversionOutcome.TAKEN
    assert consensus.outcome_agreement == 1.0
    assert not consensus.needs_review


def test_majority_wins_and_disagreement_is_flagged():
    consensus = combine(
        [
            read("returned", True, False, ["label_inspection"], dwell=6),
            read("taken", True, True, ["label_inspection", "hesitated"], dwell=8),
            read("returned", True, False, ["hesitated"], dwell=7),
        ]
    )
    assert consensus.analysis.conversion_outcome == ConversionOutcome.RETURNED
    assert consensus.outcome_agreement == 0.67
    assert consensus.review_reasons == ["Readings disagreed (2 of 3 agree)"]
    # A tag survives when most reads saw it.
    assert set(consensus.analysis.behavior_tags) == {BehaviorTag.LABEL_INSPECTION, BehaviorTag.HESITATED}
    assert consensus.analysis.zone_dwell_time_seconds == 7


def test_outcome_that_contradicts_the_observations_is_flagged():
    contradiction = read("taken", False, False)
    assert consistency_issues(contradiction) == ["Outcome says taken, but no item left the shelf"]
    assert combine([contradiction] * 3).needs_review


def test_tool_counts_match_the_dashboard_funnel():
    tools = CopilotTools(build_repository(get_settings()))
    assert tools.count_outcomes() == {
        "stopped": 17,
        "picked_up": 14,
        "taken": 9,
        "put_back": 5,
        "no_pickup": 3,
        "taken_pct_of_picked_up": 64.3,
        "put_back_pct_of_picked_up": 35.7,
    }
    cereal = tools.count_outcomes(zone_id="left_bay_cereal")
    assert (cereal["stopped"], cereal["taken"], cereal["put_back"]) == (11, 6, 3)
    assert tools.get_clip("evt_missing") == {"error": "No clip evt_missing"}


class FakeGemini:
    """Stands in for GeminiClient: answers after one counting call."""

    available = True

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def run_tools(self, *, system, contents, tools, temperature):
        result = tools["count_outcomes"](zone_id="left_bay_cereal")
        assert result["put_back"] == 3
        return self.answer, ["count_outcomes(zone_id='left_bay_cereal')"]


def test_chat_returns_the_tool_trace_and_keeps_only_known_citations():
    repo = build_repository(get_settings())
    answer = (
        '```json\n{"response": "**3 of 9** put back (33.3%), e.g. evt_1f559628d0 and evt_nope.", '
        '"suggested_followups": ["Why?"], "referenced_events": ["evt_1f559628d0"]}\n```'
    )
    chat = StoreChatService(repo, FakeGemini(answer))
    reply = chat.chat(ChatRequest(message="Put-back rate at the cereal bay?"))
    assert reply.tool_calls == ["count_outcomes(zone_id='left_bay_cereal')"]
    assert reply.referenced_events == ["evt_1f559628d0"]


def test_tool_loop_runs_requested_calls_then_returns_the_answer():
    from types import SimpleNamespace

    from google.genai import types

    from backend_service.services.gemini_client import GeminiClient

    calls_seen = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            calls_seen.append(contents[-1])
            if len(calls_seen) == 1:
                call = SimpleNamespace(name="count_outcomes", args={"zone_id": "left_bay_cereal"})
                return SimpleNamespace(
                    function_calls=[call],
                    candidates=[SimpleNamespace(content=types.Content(role="model", parts=[]))],
                    text=None,
                )
            return SimpleNamespace(function_calls=None, text="done")

    client = GeminiClient(get_settings())
    client._client = SimpleNamespace(models=FakeModels())
    tools = CopilotTools(build_repository(get_settings()))
    text, trace = client.run_tools(
        system="s", contents=["q"], tools=tools.as_functions(), temperature=0.0
    )
    assert (text, trace) == ("done", ["count_outcomes(zone_id='left_bay_cereal')"])
    # The second request carried the tool result back to Gemini.
    result = calls_seen[1].parts[0].function_response
    assert result.name == "count_outcomes" and result.response["put_back"] == 3
