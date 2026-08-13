"""LexIntake Streamlit UI — intake analysis demo."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

UI_DIR = Path(__file__).resolve().parent
ROOT = UI_DIR.parent
for path in (str(ROOT), str(UI_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from components.disclaimer import render_disclaimer
from components.footer import render_footer
from components.header import render_header
from components.result_viewer import render_results
from runner import run_intake_analysis

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

.li-hero {
  padding: 1.2rem 0 0.4rem 0;
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

    with st.sidebar:
        st.markdown("### Demo scenarios")
        choice = st.selectbox("Load example", ["(custom)"] + list(EXAMPLES.keys()))
        if choice != "(custom)" and st.button("Insert example"):
            st.session_state["case_description"] = EXAMPLES[choice]

        st.markdown("---")
        st.caption("Pipeline: plan → retrieve → tools → scoring → guardrails")

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

    render_footer()


if __name__ == "__main__":
    main()
