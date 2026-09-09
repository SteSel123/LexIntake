"""UI footer component."""

from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    st.markdown(
        """
        <div class="li-footer">
          LexIntake demo UI · screening only · not a substitute for counsel
        </div>
        """,
        unsafe_allow_html=True,
    )
