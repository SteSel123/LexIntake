"""UI header component."""

from __future__ import annotations

import streamlit as st

BRAND = "LexIntake"


def render_header() -> None:
    st.markdown(
        f"""
        <div class="li-hero">
          <div class="li-brand">{BRAND}</div>
          <p class="li-tagline">Agentic intake screening for law firms</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
