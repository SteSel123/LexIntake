"""Page footer with demo-context reminder (screening only, not counsel)."""

from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    """Render the shared footer below both Streamlit tabs."""
    st.markdown(
        """
        <div class="li-footer">
          LexIntake demo UI · screening only · not a substitute for counsel
        </div>
        """,
        unsafe_allow_html=True,
    )
