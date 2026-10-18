"""Thin Streamlit delivery client."""

import os

import streamlit as st

from ui.client import submit

st.title("Financial Research RAG Assistant")
question = st.text_area("Financial research question", max_chars=1000)
if st.button("Ask"):
    with st.spinner("Retrieving evidence and validating citations..."):
        result = submit(os.getenv("API_BASE_URL", "http://127.0.0.1:8000"), question)
    if result["status"] == "answered":
        st.success(result["answer"])
        for citation in result.get("citations", []):
            label = f"`{citation['evidence_id']}` — {citation['document_id']}"
            if isinstance(citation.get("source_url"), str):
                st.markdown(f"- [{label}]({citation['source_url']})")
            else:
                st.markdown(f"- {label}")
    elif result["status"] == "abstained":
        st.warning(f"{result['answer']} ({result.get('abstention_reason')})")
    else:
        st.error(result["message"])
