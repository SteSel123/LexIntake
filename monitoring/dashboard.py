"""Simple Streamlit dashboard for LexIntake monitoring metrics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Streamlit is required for the dashboard. Install with: pip install streamlit"
    ) from exc

try:
    from monitoring.metrics import get_metrics, reset_metrics
except ImportError:  # pragma: no cover - script execution
    from metrics import get_metrics, reset_metrics


def _safe_hist(values: list[float] | list[int], bins: int = 10) -> tuple[list[str], list[int]]:
    if not values:
        return [str(i) for i in range(bins)], [0] * bins
    nums = [float(v) for v in values]
    lo, hi = min(nums), max(nums)
    if lo == hi:
        labels = [f"{lo:.0f}"]
        return labels, [len(nums)]
    width = (hi - lo) / bins
    counts = [0] * bins
    labels = []
    for i in range(bins):
        a = lo + i * width
        b = a + width
        labels.append(f"{a:.0f}-{b:.0f}")
    for n in nums:
        idx = min(bins - 1, max(0, int((n - lo) / width)))
        counts[idx] += 1
    return labels, counts


def _demo_seed() -> None:
    """Populate deterministic demo metrics when empty (safe defaults)."""
    m = get_metrics()
    if m.sessions:
        return
    m.start_session("demo-session-1")
    m.add_tokens(1200)
    m.add_cost(0.024)
    for step, ms in [
        ("plan", 12.0),
        ("retrieve", 45.0),
        ("tools", 80.0),
        ("decision", 8.0),
        ("self-check", 5.0),
    ]:
        m.add_latency(step, ms)
    for tool, dur, ok in [
        ("check_statute_of_limitations", 11.0, True),
        ("conflict_check", 9.0, True),
        ("estimate_case_value", 14.0, True),
        ("route_lead", 10.0, True),
    ]:
        m.add_tool_call(tool, dur, ok)
    m.add_retrieval("demo", hits=4, total=10)
    m.add_lead_score(78)
    m.add_lead_score(55)
    m.add_lead_score(22)
    m.add_case_value(125000)
    m.add_case_value(42000)
    m.add_case_value(210000)
    m.add_escalation("insufficient_data")
    m.add_sol_failure()
    m.add_conflict_detected()
    m.add_attorney_route("jordan_hale")
    m.add_attorney_route("jordan_hale")
    m.add_attorney_route("sam_rivera")
    m.start_session("demo-session-2")
    m.add_tokens(800)
    m.add_cost(0.016)
    m.add_lead_score(81)
    m.add_case_value(95000)
    m.add_attorney_route("m_cruz")


def render() -> None:
    st.set_page_config(page_title="LexIntake Monitoring", layout="wide")
    st.title("LexIntake Observability")
    st.caption("In-memory metrics · no sensitive client/KB text · metadata only")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Load demo metrics", type="primary"):
            _demo_seed()
            st.rerun()
    with col_b:
        if st.button("Reset metrics"):
            reset_metrics()
            st.rerun()

    metrics = get_metrics()
    session = metrics.session_summary()
    daily = metrics.daily_summary()

    st.header("1. Session Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tokens used", session["tokens_used"])
    c2.metric("Cost (USD)", f"{session['cost']:.4f}")
    c3.metric("Total latency (ms)", f"{session['total_latency_ms']:.1f}")
    c4.metric("Tool calls", session["tool_calls"])

    c5, c6, c7 = st.columns(3)
    c5.metric("Retrieval hit rate", f"{session['retrieval_hit_rate']:.2%}")
    c6.metric("Escalations", session["escalation_count"])
    dist = session["lead_score_distribution"]
    c7.metric("Avg lead score", f"{dist['avg']:.1f}")

    st.subheader("Lead score distribution")
    labels, counts = _safe_hist(dist["values"], bins=10)
    st.bar_chart({"bucket": labels, "count": counts}, x="bucket", y="count")

    st.header("2. Daily Statistics")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Total sessions", daily["total_sessions"])
    d2.metric("Average lead score", f"{daily['average_lead_score']:.1f}")
    d3.metric("SOL failures", daily["sol_failures"])
    d4.metric("Conflicts detected", daily["conflicts_detected"])

    d5, d6 = st.columns(2)
    d5.metric("Average case value", f"${daily['average_case_value']:,.0f}")
    d6.metric("Escalation rate", f"{daily['escalation_rate']:.2%}")

    st.subheader("Attorney routing distribution")
    routes = daily["attorney_routing_distribution"] or {"none": 0}
    st.bar_chart(
        {"attorney_key": list(routes.keys()), "count": list(routes.values())},
        x="attorney_key",
        y="count",
    )

    st.header("3. Visualizations")
    left, right = st.columns(2)

    with left:
        st.subheader("Case value distribution")
        vlabels, vcounts = _safe_hist(session["case_value_distribution"]["values"], bins=8)
        st.bar_chart({"bucket": vlabels, "count": vcounts}, x="bucket", y="count")

        st.subheader("Tool usage frequency")
        usage = session["tool_usage"] or {"none": 0}
        st.bar_chart(
            {"tool": list(usage.keys()), "count": list(usage.values())},
            x="tool",
            y="count",
        )

    with right:
        st.subheader("Daily sessions over time")
        by_day = daily["sessions_by_day"] or {_day_fallback(): 0}
        days = sorted(by_day.keys())
        st.line_chart(
            {"day": days, "sessions": [by_day[d] for d in days]},
            x="day",
            y="sessions",
        )

        st.subheader("Latency by step (ms)")
        lat = session["latencies"]
        if lat:
            step_avg = {
                step: (sum(vals) / len(vals) if vals else 0.0) for step, vals in lat.items()
            }
            st.bar_chart(
                {"step": list(step_avg.keys()), "avg_ms": list(step_avg.values())},
                x="step",
                y="avg_ms",
            )
        else:
            st.info("No latency samples yet.")

    with st.expander("Raw session summary (metadata only)"):
        st.json(session)
    with st.expander("Raw daily summary (metadata only)"):
        st.json(daily)

    st.header("4. Agno Monitoring (native traces)")
    st.caption("OpenTelemetry traces stored in monitoring/traces.db via agno.tracing.setup_tracing")
    try:
        from monitoring.agno_tracing import (
            TRACES_DB,
            enable_agno_monitoring,
            recent_traces,
            tracing_enabled,
        )

        t1, t2 = st.columns(2)
        with t1:
            if st.button("Enable / refresh Agno tracing"):
                enable_agno_monitoring(force=True)
                st.rerun()
        with t2:
            st.write(
                {
                    "enabled": tracing_enabled(),
                    "traces_db": str(TRACES_DB),
                    "db_exists": TRACES_DB.exists(),
                }
            )
        traces = recent_traces(limit=15)
        if traces:
            st.dataframe(traces, use_container_width=True)
        else:
            st.info(
                "No Agno traces yet. Run an intake with a live LLM "
                "(LEXINTAKE_AGNO_TRACING=1) to populate traces.db."
            )
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Agno tracing panel unavailable: {exc}")


def _day_fallback() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    # `streamlit run monitoring/dashboard.py`
    render()
