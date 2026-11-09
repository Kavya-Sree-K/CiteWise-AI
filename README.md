# Knowledge Platform

Secure, source-grounded policy assistant (FastAPI + Streamlit + LangGraph + Chroma).

## Run (Windows, from this folder)
```
pip install -r requirements.txt
ollama pull nomic-embed-text
ollama pull qwen2.5:3b

python scripts/generate_docs.py     # 529 realistic documents (replaces data/seed)
python scripts/seed_db.py           # users, roles, documents, access lists
python scripts/ingest.py            # chunk + embed everything (first run: a few minutes)

uvicorn mock_services.main:app --port 9000      # terminal 1
uvicorn app.main:app --port 8000                # terminal 2
streamlit run ui/app.py                         # terminal 3
```
Demo logins (password `Passw0rd!`): emp1, hr1, it1, fin1, legal1, admin1.
Reset everything: delete `knowledge.db` and `data/chroma`, then run the three scripts again.

## The Ask page
By default only the friendly answer is shown. Tick **Show sources and technical
details** in the sidebar to see sources, pages, passages and the processing steps.

## Tests and evaluation
```
python -m pytest -q
python scripts/evaluate.py          # fast mode (no LLM)
python scripts/evaluate.py --llm    # with the local model
```
Good questions to try as emp1: "How do I report a security incident?",
"How many days of annual leave do I get?", "How do I reset my password?".
