"""Legal disclaimer component."""

from __future__ import annotations

import streamlit as st

DISCLAIMER = "This is not legal advice. Consult a licensed attorney."


def render_disclaimer(*, compact: bool = False) -> None:
    css_class = "li-disclaimer compact" if compact else "li-disclaimer"
    st.markdown(
        f"""
        <div class="{css_class}">
          <strong>Disclaimer:</strong> {DISCLAIMER}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_escalation_banner() -> None:
    st.markdown(
        """
        <div class="li-escalate">
          Escalated to human intake specialist.
        </div>
        """,
        unsafe_allow_html=True,
    )
