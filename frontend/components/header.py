"""Branded hero header for the LexIntake Streamlit landing area."""

from __future__ import annotations

import streamlit as st

BRAND = "LexIntake"


def render_header() -> None:
    """Render product name and tagline above the tabbed intake UI."""
    st.markdown(
        f"""
        <div class="li-hero">
          <div class="li-brand">{BRAND}</div>
          <p class="li-tagline">Agentic intake screening for law firms</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
