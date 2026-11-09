"""Comparison questions ("Compare leave for the US and Singapore") and short region names."""
from app import composer, rag


def test_short_names_are_written_the_way_documents_spell_them():
    assert "United States" in rag.expand_aliases("Compare leave for the US and Singapore")
    assert "United Kingdom" in rag.expand_aliases("What about the UK?")
    assert rag.expand_aliases("Please tell us the rule") == "Please tell us the rule"   # the word "us"


def test_comparison_words_do_not_count_as_missing_evidence():
    assert "compare" not in rag.keywords("Compare annual leave for the US and Singapore")


def test_a_comparison_gets_evidence_from_every_region_named(client, emp):
    body = client.post("/ask", headers=emp, json={
        "question": "Compare annual leave for the US and Singapore"}).json()
    assert body["status"] == "answered"
    titles = " ".join(s["title"] for s in body["sources"])
    assert "(United States)" in titles and "(Singapore)" in titles
    assert any(s["title"].startswith("Leave Policy") for s in body["sources"])


def test_one_named_region_puts_that_regions_documents_first(client, emp):
    body = client.post("/ask", headers=emp, json={
        "question": "How many days of annual leave in India?"}).json()
    assert body["status"] == "answered"
    assert body["sources"][0]["title"] == "Leave Policy (India)"


def test_a_csv_table_chunk_is_read_as_one_sentence_per_row():
    table = ("grade, annual_leave_days, sick_leave_days, notice_days, policy, version\n"
             "Associate, 22, 4, 7, Leave Policy (United States), 3\n"
             "Senior, 24, 4, 7, Leave Policy (United States), 3")
    rows = composer.sentences_of(table)
    assert rows[0].startswith("Associate: 22 days of annual leave")
    assert len(rows) == 2 and "Leave Policy" not in rows[0]


def test_normal_text_is_split_as_before():
    assert len(composer.sentences_of("First sentence here. Second sentence here.")) == 2


def test_generated_documents_are_never_dated_in_the_future(db):
    from datetime import date
    from app.models import Document
    future = (db.query(Document)
                .filter(Document.effective_date > date.today(), Document.edge_case_note == "")
                .count())
    assert future == 0