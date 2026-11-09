import uuid
from datetime import date

from app import rag
from app.chunking import build_chunks, csv_chunks, page_units
from app.models import Document, Role
from app.rag import MIN_COVERAGE, ensure_index, mmr, retrieve, rrf, verify


def role_id(db, name):
    return db.query(Role).filter(Role.name == name).first().id


# ================= CHUNKING =================
def test_chunks_never_cut_a_sentence_and_respect_the_size_limit():
    text = "\n".join(f"Sentence number {i} explains rule {i} of the policy in detail."
                     for i in range(60))
    units, _ = page_units(text)
    chunks = build_chunks(units)
    assert len(chunks) > 1
    for _, chunk in chunks:
        assert len(chunk) <= 1100
        assert chunk.endswith(".")


def test_headings_become_sections_and_page_headers_are_dropped():
    units, last = page_units("Expense Policy - Page 1\nTravel Rules\n"
                             "Book flights early. Keep receipts.\nPage 1 of 3\n")
    assert last == "Travel Rules"
    assert {sec for sec, _ in units} == {"Travel Rules"}
    assert all("Page" not in sentence for _, sentence in units)


def test_a_topic_shift_starts_a_new_chunk():
    units = [("", f"Sentence {i:02d} " + "x" * 50 + ".") for i in range(12)]
    sims = [0.80 + 0.01 * i for i in range(11)]
    sims[4] = 0.2                                   # the topic changes after sentence 4
    chunks = build_chunks(units, sims)
    assert len(chunks) == 2
    assert "Sentence 04" in chunks[0][1] and "Sentence 05" not in chunks[0][1]


def test_csv_chunks_repeat_the_header_row():
    rows = "id,name\n" + "\n".join(f"{i},item{i}" for i in range(30))
    chunks = csv_chunks(rows, rows_per_chunk=12)
    assert len(chunks) == 3
    assert all(text.startswith("id, name") for _, text in chunks)
    assert chunks[0][0] == "Rows 1-12"


# ================= RANKING AND VERIFICATION =================
def test_rank_fusion_prefers_chunks_found_by_both_searches():
    order, _ = rrf([[1, 2, 3], [2, 3, 4]])
    assert order[0] == 2


def test_mmr_skips_a_near_duplicate_chunk():
    embs = {1: [1.0, 0.0], 2: [1.0, 0.0], 3: [0.0, 1.0]}
    relevance = {1: 1.0, 2: 0.99, 3: 0.8}
    assert mmr([1, 2, 3], embs, relevance, 2) == [1, 3]


def test_a_paraphrased_question_passes_only_with_high_similarity():
    chunk = {"title": "Salary Policy", "text": "pay rules for staff", "sim": 0.9}
    assert verify("compensation rules fortnight", [chunk]) == MIN_COVERAGE
    chunk["sim"] = 0.5
    assert verify("compensation rules fortnight", [chunk]) < MIN_COVERAGE


def test_follow_up_with_new_subject_words_is_not_joined_to_the_old_question():
    plan = rag.route("and what about annual leave?", ["What is the expense policy limit?"])
    assert "expense" not in plan["query"]


# ================= DOCUMENT RULES IN RETRIEVAL =================
def test_future_dated_document_is_not_used_until_it_takes_effect(client, admin_a, db):
    tag = "zephyr" + uuid.uuid4().hex[:8]
    r = client.post("/admin/upload", headers=admin_a,
                    data={"department": "HR", "owner": "Test Owner",
                          "sensitivity": "Internal", "effective_date": "2099-01-01",
                          "title": f"{tag} Policy"},
                    files={"file": ("future.txt", f"{tag} policy. The limit is 7 days.".encode())})
    assert r.status_code == 200
    doc_id = r.json()["document_id"]
    rows = client.get("/admin/all-documents", headers=admin_a).json()
    info = next(d for d in rows if d["id"] == doc_id)
    assert info["status"] == "active" and info["ingestion"] == "done"
    ensure_index(db)
    found = retrieve(db, role_id(db, "admin"), tag, None, top=10)
    assert all(c["document_id"] != doc_id for c in found)


def test_search_falls_back_to_keyword_only_when_embeddings_fail(monkeypatch, db):
    def down(*args, **kwargs):
        raise RuntimeError("embedding model down")

    monkeypatch.setattr(rag, "embed", down)
    ensure_index(db)
    doc = (db.query(Document)
             .filter(Document.status == "active", Document.ingestion_status == "done",
                     Document.effective_date <= date.today()).first())
    found = retrieve(db, role_id(db, "admin"), doc.title, None, top=5)
    assert found and found[0]["mode"] == "keyword only"