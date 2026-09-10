"""Legal disclaimer and escalation banners for user-facing Streamlit output.

Every screening result must show the non-advice disclaimer; escalation uses a
distinct visual treatment so staff notice human-review cases immediately.
"""

from __future__ import annotations

import streamlit as st

DISCLAIMER = "This is not legal advice. Consult a licensed attorney."


def render_disclaimer(*, compact: bool = False) -> None:
    """Render the standard legal disclaimer (compact variant for page header)."""
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
    """Highlight cases routed to a human intake specialist."""
    st.markdown(
        """
        <div class="li-escalate">
          Escalated to human intake specialist.
        </div>
        """,
        unsafe_allow_html=True,
    )
