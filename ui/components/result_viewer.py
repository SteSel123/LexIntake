"""Result viewer for intake analysis output."""

from __future__ import annotations

from typing import Any

import streamlit as st

from components.disclaimer import render_disclaimer, render_escalation_banner


def render_results(payload: dict[str, Any]) -> None:
    if payload.get("escalate"):
        render_escalation_banner()

    render_disclaimer()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Qualified", "Yes" if payload.get("qualified") else "No")
    c2.metric("Lead score", payload.get("lead_score", "—"))
    c3.metric("Priority", payload.get("priority", "—"))
    c4.metric("Decision", payload.get("decision", "—"))

    st.subheader("Lead Qualification")
    st.write(
        f"**Qualified:** `{payload.get('qualified')}`  \n"
        f"**Recommended attorney:** `{payload.get('recommended_attorney')}`  \n"
        f"**Latency:** `{payload.get('latency_ms', 0):.1f} ms`  \n"
        f"**Cost:** `${float(payload.get('cost') or 0):.4f}`"
    )

    st.subheader("Explanation")
    st.write(payload.get("explanation") or "No explanation available.")

    st.subheader("KB Citations")
    citations = payload.get("citations") or []
    if not citations:
        st.info("No KB citations returned.")
    else:
        for cite in citations:
            st.markdown(
                f"- `chunk_id={cite.get('chunk_id')}` · "
                f"`practice_area={cite.get('practice_area')}` · "
                f"`doc_type={cite.get('doc_type')}`"
            )

    st.subheader("Guardrails")
    guards = payload.get("guardrails") or {}
    st.write(
        {
            "disclaimer_present": bool(guards.get("disclaimer_present")),
            "citations_present": bool(guards.get("citations_present")),
            "escalation_flag": bool(guards.get("escalation_flag") or payload.get("escalate")),
            "legal_disclaimer": "This is not legal advice. Consult a licensed attorney.",
        }
    )

    with st.expander("Tool results (metadata)"):
        st.json(payload.get("tool_results") or {})

    st.subheader("Raw JSON output")
    display = {
        "qualified": payload.get("qualified"),
        "lead_score": payload.get("lead_score"),
        "priority": payload.get("priority"),
        "decision": payload.get("decision"),
        "recommended_attorney": payload.get("recommended_attorney"),
        "explanation": payload.get("explanation"),
        "citations": payload.get("citations") or [],
    }
    st.json(display)
