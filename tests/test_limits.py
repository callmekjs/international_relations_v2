from assistant.limits import QA_CAPS, Budget, TurnPlan
from assistant.llm import Usage


def test_qa_caps_follow_the_spec():
    assert (QA_CAPS.tool_calls, QA_CAPS.input_tokens, QA_CAPS.output_tokens, QA_CAPS.output_per_call) == (
        10, 120_000, 30_000, 8_000)


def test_first_turn_may_use_tools():
    assert Budget(QA_CAPS).plan_next_turn(4_000) == TurnPlan(True, "auto", 8_000)


def test_tool_cap_blocks_tools():
    budget = Budget(QA_CAPS)
    for _ in range(10):
        budget.record_tool_call()
    assert budget.tool_calls_left() == 0
    assert budget.plan_next_turn(1_000) == TurnPlan(True, "none", 8_000)


def test_tools_stop_while_there_is_still_room_for_an_answer():
    tight = Budget(QA_CAPS)
    tight.record_turn(Usage(input=30_000, output=1_000))
    assert tight.plan_next_turn(10_000) == TurnPlan(True, "none", 8_000)  # 41K now + 41K + 16K later > 90K left
    roomy = Budget(QA_CAPS)
    roomy.record_turn(Usage(input=20_000, output=1_000))
    assert roomy.plan_next_turn(5_000).tool_choice == "auto"             # 26K + 26K + 16K <= 100K left


def test_no_turn_is_sent_past_the_input_cap():
    budget = Budget(QA_CAPS)
    budget.record_turn(Usage(input=60_000, output=1_000))
    assert budget.plan_next_turn(5_000) == TurnPlan(False, "none", 0)     # 66K > 60K left


def test_output_cap_keeps_room_for_the_answer():
    budget = Budget(QA_CAPS)
    budget.record_turn(Usage(input=1_000, output=20_000))
    assert budget.plan_next_turn(100) == TurnPlan(True, "none", 8_000)
    budget.record_turn(Usage(input=1_000, output=5_000))
    assert budget.plan_next_turn(100) == TurnPlan(True, "none", 5_000)
    budget.record_turn(Usage(input=1_000, output=5_000))
    assert budget.plan_next_turn(100).send is False
