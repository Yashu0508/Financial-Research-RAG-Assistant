# Thin UI

Run FastAPI first, then install the optional UI dependency and start Streamlit:

```bash
python -m uvicorn app.main:app --reload
python -m pip install -e ".[ui]"
streamlit run ui/app.py
```

`API_BASE_URL` defaults to `http://127.0.0.1:8000`. The UI only POSTs a question
to `/query`; it never imports retrieval, database, or provider code. It renders
typed answers, abstentions, warnings, and API-resolved citation links. A live
query additionally requires the guarded local corpus, cached models, and Phase
8 OpenAI configuration. Tests use mock pipelines and make no provider call.
