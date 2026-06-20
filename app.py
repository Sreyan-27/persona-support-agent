"""
app.py
------
Streamlit chat UI for the Persona-Adaptive Support Agent (bonus interface).

Run with:
    streamlit run app.py

Displays, per the assignment spec: user message, detected persona,
retrieved sources, generated response, and escalation status, in a
chat-style interface with full conversation history.
"""

import json

import streamlit as st

from src.config import validate_settings
from src.rag_pipeline import LocalRAGPipeline
from src.session import SupportSession

st.set_page_config(page_title="TechCorp Cloud Support Agent", page_icon="💬", layout="centered")


@st.cache_resource(show_spinner="Loading knowledge base and embedding documents (first run only)...")
def get_pipeline():
    pipeline = LocalRAGPipeline()
    pipeline.ingest_all()
    return pipeline


def persona_badge(persona: str) -> str:
    colors = {
        "Technical Expert": "🔧",
        "Frustrated User": "💛",
        "Business Executive": "📊",
    }
    return f"{colors.get(persona, '')} **{persona}**"


def main():
    st.title("💬 TechCorp Cloud Support Agent")
    st.caption("Persona-adaptive customer support, powered by Gemini + RAG")

    problems = validate_settings()
    for p in problems:
        st.warning(p)

    if "session" not in st.session_state:
        pipeline = get_pipeline()
        st.session_state.session = SupportSession(pipeline=pipeline)
        st.session_state.display_history = []

    # Sidebar: live session stats
    with st.sidebar:
        st.header("Session Info")
        sess = st.session_state.session
        st.metric("Turns this session", len(sess.history) // 2)
        st.metric("Unresolved streak", sess.unresolved_turns)
        st.divider()
        st.subheader("Knowledge Base")
        try:
            doc_count = sess.pipeline.collection.count()
            st.write(f"{doc_count} indexed chunks")
        except Exception:
            pass
        if st.button("🔄 Re-ingest knowledge base (force)"):
            with st.spinner("Re-indexing..."):
                sess.pipeline.ingest_all(force=True)
            st.success("Re-ingested.")
        if st.button("🗑️ Reset conversation"):
            del st.session_state.session
            del st.session_state.display_history
            st.rerun()

    # Render prior turns
    for turn in st.session_state.display_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
            if turn.get("meta"):
                st.caption(turn["meta"])

    user_input = st.chat_input("Type your support question...")
    if user_input:
        st.session_state.display_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = st.session_state.session.send(user_input)

            persona_line = persona_badge(result["persona"]) + f"  ·  confidence {result['persona_confidence']:.2f}"
            st.markdown(persona_line)

            if result["retrieved_sources"]:
                with st.expander(f"📚 Retrieved sources ({len(result['retrieved_sources'])})"):
                    for s in result["retrieved_sources"]:
                        locator = f"page {s['page']}" if s.get("page") else (s.get("section") or "")
                        st.write(f"- **{s['source']}** {f'({locator})' if locator else ''} — score {s['score']:.2f}")

            if result["escalated"]:
                st.error("🚨 Escalated to a human support specialist")
                st.caption("Triggers: " + ", ".join(result["escalation_triggers"]))
            else:
                st.success("✅ Resolved by agent")

            st.markdown(result["response"])

            if result["handoff_summary"]:
                with st.expander("🗂️ Human Handoff Summary"):
                    st.code(json.dumps(result["handoff_summary"], indent=2), language="json")

            meta = f"{result['persona']} · {'Escalated' if result['escalated'] else 'Resolved'}"
            st.session_state.display_history.append(
                {"role": "assistant", "content": result["response"], "meta": meta}
            )


if __name__ == "__main__":
    main()
