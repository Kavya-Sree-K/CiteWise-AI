from app.composer import build_result, extractive, parse_json, with_sources

CHUNKS = [
    {"title": "Expense Policy (Effort Unit)", "version": 3, "page": 1,
     "text": "Under Expense Policy (Effort Unit) (version 3), the standard limit is 51 days.",
     "context_text": "Under Expense Policy (Effort Unit) (version 3), the standard limit is 51 days. Receipts are required."},
    {"title": "Expense Policy (Show Unit)", "version": 3, "page": 1,
     "text": "Under Expense Policy (Show Unit) (version 3), the standard limit is 22 days."},
]


def good():
    return {"enough_information": True,
            "answer": "The standard limit in the Expense Policy (Effort Unit) is 51 days [1].",
            "details": ["Receipts are required [1]."], "steps": [], "comparison": [],
            "follow_ups": ["What is the limit for the Show Unit?"], "sources_used": [1]}


def test_a_grounded_answer_is_accepted_with_its_extras():
    result = build_result(good(), CHUNKS)
    assert result["answer"].endswith("[1].")
    assert result["details"] and result["follow_ups"] and result["used"] == {1}


def test_an_invented_number_is_rejected():
    bad = good()
    bad["answer"] = "The standard limit in the Expense Policy (Effort Unit) is 99 days [1]."
    assert build_result(bad, CHUNKS) is None


def test_a_citation_to_a_missing_source_is_rejected():
    bad = good()
    bad["answer"] = "The standard limit in the Expense Policy (Effort Unit) is 51 days [5]."
    assert build_result(bad, CHUNKS) is None


def test_an_invented_detail_is_dropped_but_the_answer_survives():
    data = good()
    data["details"] = ["Receipts are required [1].", "Managers get a free lunch with 12 coupons."]
    assert build_result(data, CHUNKS)["details"] == ["Receipts are required [1]."]


def test_the_model_can_say_it_does_not_know():
    assert build_result({"enough_information": False, "answer": ""}, CHUNKS) == {"not_enough": True}


def test_a_comparison_table_needs_two_supported_rows():
    data = good()
    data["comparison"] = [{"label": "Effort Unit", "value": "51 days", "source": 1},
                          {"label": "Show Unit", "value": "22 days", "source": 2}]
    assert len(build_result(data, CHUNKS)["comparison"]) == 2
    data["comparison"] = [{"label": "Effort Unit", "value": "51 days", "source": 1},
                          {"label": "Show Unit", "value": "40 days", "source": 2}]
    assert build_result(data, CHUNKS)["comparison"] == []


def test_steps_are_kept_only_when_there_are_three_or_more():
    data = good()
    data["steps"] = ["Receipts are required [1].", "The standard limit is 51 days [1]."]
    assert build_result(data, CHUNKS)["procedure"] == []


def test_broken_json_is_handled_and_the_fallback_quotes_the_best_sentence():
    assert parse_json("Sure! {\"a\": 1}") == {"a": 1}
    assert parse_json("no json here") is None
    result = with_sources("standard limit Show Unit", CHUNKS, extractive("standard limit Show Unit", CHUNKS))
    assert "22 days" in result["answer"]
    assert result["sources"][1]["used"] is True and result["sources"][0]["used"] is False
