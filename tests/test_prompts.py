from assistant.prompts import QA_ANSWER_FORMAT, QA_INSTRUCTIONS, STATUSES, qa_user_text
from tests.schema_check import strict_schema_problems


def test_answer_format_is_strict_and_lists_the_statuses():
    schema = QA_ANSWER_FORMAT["schema"]
    assert QA_ANSWER_FORMAT["name"] == "qa_answer"
    assert strict_schema_problems(schema) == []
    assert tuple(schema["properties"]["status"]["enum"]) == STATUSES
    citation = schema["properties"]["sentences"]["items"]["properties"]["citations"]["items"]
    assert citation["required"] == ["page_id", "paragraph", "quote"]


def test_prompt_uses_only_plain_characters_and_names_every_tool_and_status():
    odd = {c for c in QA_INSTRUCTIONS if ord(c) > 127 and not 0xAC00 <= ord(c) <= 0xD7A3}
    assert odd == set()
    for word in ("search", "read_pages", "get_toc", "paragraph", "quote", *STATUSES):
        assert word in QA_INSTRUCTIONS


def test_user_text_adds_the_year_scope():
    assert qa_user_text("한미 정상회담은?", None) == "한미 정상회담은?"
    assert qa_user_text("한미 정상회담은?", [2024, 2023]) == "한미 정상회담은?\n(연도 범위: 2023년치, 2024년치)"
