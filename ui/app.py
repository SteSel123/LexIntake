"""LexIntake Streamlit UI — multi-turn interview + quick analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

UI_DIR = Path(__file__).resolve().parent
ROOT = UI_DIR.parent
for path in (str(ROOT), str(UI_DIR), str(ROOT / "agents")):
    if path not in sys.path:
        sys.path.insert(0, path)

from components.disclaimer import render_disclaimer
from components.footer import render_footer
from components.header import render_header
from components.result_viewer import render_results
from runner import LEGAL_DISCLAIMER, build_result_payload, run_intake_analysis

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Source+Sans+3:wght@400;600;700&display=swap');

:root {
  --ink: #14212b;
  --muted: #5b6b75;
  --paper: #f3efe6;
  --panel: #fffdf8;
  --line: #d7d0c3;
  --accent: #0f6a5c;
  --accent-2: #c45c26;
  --danger: #8b2e2e;
}

.stApp {
  background:
    radial-gradient(1200px 500px at 10% -10%, #e7f2ef 0%, transparent 55%),
    linear-gradient(180deg, #f7f3ea 0%, #efe8da 100%);
  color: var(--ink);
  font-family: "Source Sans 3", sans-serif;
}

.li-brand {
  font-family: Fraunces, Georgia, serif;
  font-size: 3rem;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ink);
  margin: 0;
}
.li-tagline {
  margin: 0.55rem 0 0.2rem 0;
  color: var(--muted);
  font-size: 1.05rem;
}
.li-disclaimer {
  border: 1px solid var(--line);
  background: var(--panel);
  border-left: 4px solid var(--accent);
  padding: 0.85rem 1rem;
  margin: 0.75rem 0 1rem 0;
}
.li-escalate {
  background: #f8e8e4;
  border: 1px solid #e2b4a8;
  color: var(--danger);
  font-weight: 700;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 1rem 0;
}
.li-footer {
  margin-top: 2rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.92rem;
}
div[data-testid="stMetric"] {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 0.75rem;
}

/* Chat / markdown: force readable dark ink on light theme */
[data-testid="stChatMessage"],
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] .stMarkdown,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
.stMarkdown, .stMarkdown p {
  color: var(--ink) !important;
}
[data-testid="stChatMessage"] {
  background: var(--panel) !important;
  border: 1px solid var(--line);
  border-radius: 8px;
}
[data-testid="stCaption"],
.stCaption, small {
  color: var(--muted) !important;
}
h1, h2, h3, h4, .stHeading, [data-testid="stHeading"] {
  color: var(--ink) !important;
}
"""

EXAMPLES = {
    "Valid Personal Injury": (
        "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
    ),
    "SOL Expired": (
        "Slip-and-fall in NV, incident 4 years ago, moderate injuries."
    ),
    "Conflict Case": (
        "Employment discrimination claim in CA, opposing party is ACME Corp."
    ),
    "Uncertain / Review": (
        "Immigration matter with unclear facts, missing dates, missing jurisdiction."
    ),
}


def _ensure_interview():
    from agents.interview import InterviewSession

    if "interview" not in st.session_state:
        session = InterviewSession()
        opening = session.start()
        st.session_state["interview"] = session
        st.session_state["interview_messages"] = [
            {"role": "assistant", "content": opening.assistant_message}
        ]
        st.session_state["interview_done"] = False
        st.session_state.pop("interview_result", None)


def _render_interview_tab() -> None:
    st.markdown("### Prospective client interview")
    st.caption(
        "Multi-turn intake: the agent asks follow-up questions, then screens the lead. "
        + LEGAL_DISCLAIMER
    )

    _ensure_interview()

    cols = st.columns([1, 1, 2])
    if cols[0].button("Restart interview"):
        st.session_state.pop("interview", None)
        st.session_state.pop("interview_messages", None)
        st.session_state.pop("interview_done", None)
        st.session_state.pop("interview_result", None)
        _ensure_interview()
        st.rerun()

    for msg in st.session_state.get("interview_messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.get("interview_done"):
        st.info("Interview complete. Restart to screen another lead.")
        if "interview_result" in st.session_state:
            st.markdown("## Screening result")
            render_results(st.session_state["interview_result"])
        return

    prompt = st.chat_input("Answer the agent’s question or describe your matter…")
    if not prompt:
        return

    st.session_state["interview_messages"].append({"role": "user", "content": prompt})
    session = st.session_state["interview"]
    with st.spinner("Updating intake…"):
        turn = session.respond(prompt)
    st.session_state["interview_messages"].append(
        {"role": "assistant", "content": turn.assistant_message}
    )

    if turn.done and turn.screening is not None:
        st.session_state["interview_done"] = True
        narrative = turn.facts.narrative or prompt
        payload = build_result_payload(turn.screening, turn.facts, narrative)
        payload["latency_ms"] = float(getattr(turn.screening, "latency_ms", 0) or 0)
        payload["cost"] = float(getattr(turn.screening, "cost", 0) or 0)
        payload["parsed_facts"] = turn.facts.model_dump()
        st.session_state["interview_result"] = payload
    st.rerun()


def _render_quick_tab() -> None:
    with st.sidebar:
        st.markdown("### Demo scenarios")
        choice = st.selectbox("Load example", ["(custom)"] + list(EXAMPLES.keys()))
        if choice != "(custom)" and st.button("Insert example"):
            st.session_state["case_description"] = EXAMPLES[choice]
        st.markdown("---")
        st.caption("Single-pass: plan → retrieve → tools → scoring → guardrails")

    description = st.text_area(
        "Case description",
        value=st.session_state.get("case_description", ""),
        height=160,
        placeholder=(
            "Example: Rear-end collision in CA, clear liability, $45k damages, "
            "incident 6 months ago."
        ),
        key="case_description",
    )

    run = st.button("Run Intake Analysis", type="primary")
    if run:
        if not description.strip():
            st.warning("Enter a case description first.")
            return
        with st.spinner("Running intake pipeline..."):
            try:
                payload = run_intake_analysis(description.strip())
                st.session_state["last_result"] = payload
            except Exception as exc:  # noqa: BLE001
                st.error(f"Intake analysis failed: {exc}")
                return

    if "last_result" in st.session_state:
        st.markdown("## Analysis result")
        render_results(st.session_state["last_result"])


def main() -> None:
    st.set_page_config(
        page_title="LexIntake",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

    render_header()
    render_disclaimer(compact=True)

    try:
        from config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            st.warning(
                "OPENAI_API_KEY is empty in `.env`. "
                "Set a new key for live embeddings/LLM; offline hash/deterministic still works for demos."
            )
    except Exception:  # noqa: BLE001
        pass

    tab_interview, tab_quick = st.tabs(["Interview (multi-turn)", "Quick analysis"])
    with tab_interview:
        _render_interview_tab()
    with tab_quick:
        _render_quick_tab()

    render_footer()


if __name__ == "__main__":
    main()
