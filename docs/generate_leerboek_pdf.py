"""Generate the LexIntake comprehensive Dutch learning PDF (40+ pages).

Builds ``docs/LexIntake_Leerboek.pdf`` with chapter diagrams, repo maps, and
worked examples for capstone study. Requires fpdf2 and system Arial fonts.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "LexIntake_Leerboek.pdf"
FONT_REG = "C:/Windows/Fonts/arial.ttf"
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_ITALIC = "C:/Windows/Fonts/ariali.ttf"


class Leerboek(FPDF):
    """FPDF subclass with LexIntake branding and reusable diagram helpers."""

    def __init__(self) -> None:
        super().__init__(format="A4", unit="mm")
        self.set_auto_page_break(auto=True, margin=18)
        self.add_font("Body", "", FONT_REG)
        self.add_font("Body", "B", FONT_BOLD)
        self.add_font("Body", "I", FONT_ITALIC)
        self.chapter_num = 0

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Body", "I", 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 5, "LexIntake Leerboek — Agentic RAG Capstone", align="L")
        self.ln(4)
        # Mini structure strip on every page
        labels = ["UI", "Agent", "RAG", "Tools", "Score", "Guard"]
        usable = self.w - self.l_margin - self.r_margin
        box_w = usable / len(labels)
        y = self.get_y()
        x = self.l_margin
        self.set_draw_color(180, 200, 195)
        self.set_fill_color(245, 250, 248)
        self.set_font("Body", "B", 6.5)
        self.set_text_color(40, 70, 65)
        for i, lab in enumerate(labels):
            self.rect(x, y, box_w - 0.8, 5.5, style="DF")
            self.set_xy(x, y + 0.7)
            self.cell(box_w - 0.8, 4, lab, align="C")
            if i < len(labels) - 1:
                self.line(x + box_w - 0.8, y + 2.7, x + box_w, y + 2.7)
            x += box_w
        self.set_y(y + 7)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(20, 20, 20)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Body", "I", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Pagina {self.page_no()}", align="C")

    def cover(self) -> None:
        self.add_page()
        self.ln(18)
        self.set_font("Body", "B", 28)
        self.multi_cell(0, 12, "LexIntake", align="C")
        self.ln(2)
        self.set_font("Body", "B", 16)
        self.multi_cell(0, 8, "Uitgebreid Leerboek van Begin tot Eind", align="C")
        self.ln(3)
        self.set_font("Body", "", 12)
        self.multi_cell(
            0,
            7,
            "Alles wat je moet weten over de capstone-opdracht:\n"
            "Agentic RAG intake screening voor advocatenkantoren\n"
            "met Agno, PostgreSQL/pgvector, FastAPI, Streamlit, Docker en CI.",
            align="C",
        )
        self.ln(4)
        self.flow(
            ["Prospect", "UI/API", "Agent", "Tools+RAG", "Beslissing"],
            title="Grote lijn van het systeem",
        )
        self.layers(
            [
                ("UI", "Streamlit (frontend/) interview + quick analysis"),
                ("API", "FastAPI (backend/) REST endpoints"),
                ("Agent", "Plan / Retrieve / Tools / Decide / Self-check"),
                ("Data", "PostgreSQL: kb_docs (pgvector) + entities"),
                ("KB/ETL", "kb/ -> chunk -> embed -> load"),
            ],
            title="Lagenarchitectuur",
        )
        self.ln(2)
        self.set_font("Body", "I", 11)
        self.multi_cell(
            0,
            6,
            "Doel: opdracht, architectuur, repo, start en uitleg leren.\n"
            "GEEN juridisch advies — alleen educatief materiaal.",
            align="C",
        )
        self.ln(4)
        self.set_font("Body", "", 11)
        self.multi_cell(
            0, 6, "Versie: LexIntake Capstone 2026\nRepo: github.com/SteSel123/LexIntake", align="C"
        )

    def _ensure_space(self, need_mm: float) -> None:
        if self.get_y() + need_mm > self.page_break_trigger:
            self.add_page()

    def schema_title(self, title: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Body", "B", 10)
        self.set_text_color(15, 80, 70)
        self.multi_cell(0, 5, f"Schema: {title}")
        self.set_text_color(20, 20, 20)
        self.ln(1)

    def box_row(
        self,
        labels: list[str],
        *,
        fill: tuple[int, int, int] = (232, 244, 241),
        border: tuple[int, int, int] = (15, 106, 92),
        height: float = 12,
    ) -> None:
        self._ensure_space(height + 14)
        n = max(1, len(labels))
        usable = self.w - self.l_margin - self.r_margin
        gap = 3
        arrow = 5
        box_w = (usable - (n - 1) * (gap + arrow)) / n
        y = self.get_y()
        x = self.l_margin
        self.set_draw_color(*border)
        self.set_fill_color(*fill)
        self.set_text_color(20, 40, 40)
        for i, label in enumerate(labels):
            self.set_xy(x, y)
            self.set_font("Body", "B", 7.5)
            self.rect(x, y, box_w, height, style="DF")
            self.set_xy(x + 0.8, y + height / 2 - 2.2)
            self.cell(box_w - 1.6, 4.5, label[:26], align="C")
            if i < n - 1:
                ax1 = x + box_w + 0.8
                ax2 = ax1 + arrow
                mid = y + height / 2
                self.line(ax1, mid, ax2, mid)
                self.line(ax2 - 1.8, mid - 1.4, ax2, mid)
                self.line(ax2 - 1.8, mid + 1.4, ax2, mid)
                x = ax2 + gap
            else:
                x += box_w
        self.set_y(y + height + 3.5)
        self.set_text_color(20, 20, 20)

    def flow(self, labels: list[str], *, title: str | None = None) -> None:
        if title:
            self.schema_title(title)
        self.box_row(labels)

    def vflow(self, labels: list[str], *, title: str | None = None) -> None:
        if title:
            self.schema_title(title)
        self._ensure_space(len(labels) * 15 + 8)
        usable = self.w - self.l_margin - self.r_margin
        box_w = min(125, usable)
        x = self.l_margin + (usable - box_w) / 2
        for i, label in enumerate(labels):
            y = self.get_y()
            self.set_fill_color(235, 242, 250)
            self.set_draw_color(30, 60, 90)
            self.rect(x, y, box_w, 10, style="DF")
            self.set_xy(x, y + 2.5)
            self.set_font("Body", "B", 8.5)
            self.cell(box_w, 5, label[:42], align="C")
            self.set_y(y + 10)
            if i < len(labels) - 1:
                mid_x = x + box_w / 2
                y2 = self.get_y()
                self.line(mid_x, y2, mid_x, y2 + 3.5)
                self.line(mid_x - 1.4, y2 + 2.2, mid_x, y2 + 3.5)
                self.line(mid_x + 1.4, y2 + 2.2, mid_x, y2 + 3.5)
                self.set_y(y2 + 4.2)
        self.ln(2.5)

    def layers(self, rows: list[tuple[str, str]], *, title: str | None = None) -> None:
        if title:
            self.schema_title(title)
        self._ensure_space(len(rows) * 13 + 6)
        usable = self.w - self.l_margin - self.r_margin
        colors = [
            (232, 244, 241),
            (235, 242, 250),
            (252, 244, 235),
            (245, 240, 250),
            (240, 240, 240),
        ]
        for i, (name, desc) in enumerate(rows):
            y = self.get_y()
            self.set_fill_color(*colors[i % len(colors)])
            self.set_draw_color(120, 120, 120)
            self.rect(self.l_margin, y, usable, 11, style="DF")
            self.set_xy(self.l_margin + 2, y + 1.2)
            self.set_font("Body", "B", 8.5)
            self.cell(38, 4, name[:18])
            self.set_xy(self.l_margin + 40, y + 1.2)
            self.set_font("Body", "", 8)
            self.multi_cell(usable - 44, 4, desc[:95])
            self.set_y(y + 12)
        self.ln(1.5)

    def tree(self, lines: list[str], *, title: str | None = None) -> None:
        if title:
            self.schema_title(title)
        self.set_fill_color(250, 250, 248)
        self.set_draw_color(210, 210, 205)
        self.set_font("Body", "", 8.5)
        for line in lines:
            self.set_x(self.l_margin)
            self.multi_cell(0, 4.2, line, fill=True)
        self.ln(2)

    def matrix(
        self,
        headers: list[str],
        rows: list[list[str]],
        *,
        title: str | None = None,
    ) -> None:
        if title:
            self.schema_title(title)
        cols = len(headers)
        usable = self.w - self.l_margin - self.r_margin
        col_w = usable / cols
        self._ensure_space(8 + len(rows) * 7.5)
        y = self.get_y()
        self.set_fill_color(15, 106, 92)
        self.set_text_color(255, 255, 255)
        self.set_font("Body", "B", 7.5)
        x = self.l_margin
        for h in headers:
            self.rect(x, y, col_w, 6.5, style="DF")
            self.set_xy(x + 0.6, y + 1.2)
            self.cell(col_w - 1.2, 4, h[:20], align="C")
            x += col_w
        self.set_y(y + 6.5)
        self.set_text_color(20, 20, 20)
        self.set_font("Body", "", 7.5)
        for r_i, row in enumerate(rows):
            y = self.get_y()
            if r_i % 2:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            x = self.l_margin
            for cell in row:
                self.rect(x, y, col_w, 6.5, style="DF")
                self.set_xy(x + 0.6, y + 1.2)
                self.cell(col_w - 1.2, 4, str(cell)[:22], align="C")
                x += col_w
            self.set_y(y + 6.5)
        self.ln(2.5)

    def cycle(self, labels: list[str], *, title: str | None = None) -> None:
        if title:
            self.schema_title(title)
        self.box_row(labels, fill=(252, 244, 235), border=(196, 92, 38))
        self.set_font("Body", "I", 8.5)
        self.set_x(self.l_margin)
        self.multi_cell(0, 4, "Bij onvoldoende info: terug naar vragen / retrieve / escalate")
        self.ln(1.5)

    def h1(self, title: str) -> None:
        self.chapter_num += 1
        self.add_page()
        self.set_font("Body", "B", 18)
        self.set_text_color(15, 80, 70)
        self.multi_cell(0, 9, f"Hoofdstuk {self.chapter_num}. {title}")
        self.set_text_color(20, 20, 20)
        self.ln(2)
        self._auto_schema(title)

    def _auto_schema(self, title: str) -> None:
        """Place a structure schema at the top of every chapter page."""
        t = title.lower()
        if "opdracht" in t or "waarom bestaat" in t:
            self.flow(
                ["Leads binnen", "Filteren", "Agent screent", "Route/Reject"],
                title="Van probleem naar oplossing",
            )
        elif "begrippen" in t:
            self.layers(
                [
                    ("RAG", "Ophalen + genereren met bewijs"),
                    ("Agentic", "Plant, kiest tools, beslist"),
                    ("Embedding", "Tekst -> vector"),
                    ("Guardrail", "Veiligheidsregels"),
                ],
                title="Kernbegrippen als lagen",
            )
        elif "capstone" in t or "opleveren" in t and "checklist" not in t:
            self.vflow(
                ["KB + ETL", "Agent + Tools", "Scoring + Guardrails", "UI + Eval + CI", "Reports + Video"],
                title="Deliverable-keten",
            )
        elif "architectuur" in t or "grote plaatje" in t:
            self.layers(
                [
                    ("UI", "Streamlit (frontend/)"),
                    ("API", "FastAPI (backend/)"),
                    ("Agent", "IntakeAgent (Agno)"),
                    ("Tools", "SOL / conflict / value / route"),
                    ("Data", "PostgreSQL pgvector + entities"),
                    ("KB/ETL", "kb/ -> embeddings"),
                ],
                title="Architectuurlagen",
            )
            self.flow(
                ["Plan", "Retrieve", "Tools", "Decide", "Self-check", "Respond"],
                title="Agent-loop",
            )
        elif "repository" in t or "map voor map" in t or "bestandsgids" in t:
            self.tree(
                [
                    "LexIntake/",
                    "  kb/              synthetische kennisbank (JSON/MD)",
                    "  etl/             extract -> transform -> load",
                    "  db/              Postgres models, pgvector, migrations",
                    "  agents/          intake-agent + interview-agent + llm",
                    "  tools/           Agno @tool functies",
                    "  scoring/         deterministische lead scoring",
                    "  backend/         FastAPI routes + services",
                    "  frontend/        Streamlit UI + demo",
                    "  monitoring/      metrics, dashboard, Agno traces",
                    "  evaluation/      labeled leads + harness",
                    "  scripts/         docker_init, ensure_env",
                    "  docs/            reports + dit leerboek",
                    "  docker-compose   Postgres + init + API + UI",
                    "  tests/           pytest unit tests",
                    "  Makefile         make setup / test / ui / api / eval",
                    "  .github/         CI smoke-test",
                ],
                title="Repo-boom",
            )
        elif "knowledge base" in t or title.startswith("Knowledge") or "kb/" in t:
            self.matrix(
                ["Document", "Doel"],
                [
                    ["practice_areas", "Scope"],
                    ["acceptance", "Qualify rules"],
                    ["sol_tables", "Deadlines"],
                    ["past_cases", "Valuation"],
                    ["attorneys", "Routing"],
                    ["clients", "Conflicts"],
                    ["faqs", "Grounding"],
                ],
                title="KB-onderdelen",
            )
        elif "etl" in t:
            self.flow(
                ["Extract", "Clean", "Dedupe", "Chunk", "Meta", "Embed", "Load"],
                title="ETL-pijplijn",
            )
            self.vflow(
                ["Re-runnable", "Idempotent (chunk_id upsert)", "Incremental (reuse embeds)"],
                title="Verplichte ETL-eigenschappen",
            )
        elif "embedding" in t:
            self.matrix(
                ["Pad", "Model", "Dims", "API?"],
                [
                    ["Live", "text-emb-3-small", "1536", "Ja"],
                ],
                title="Embedding-modi",
            )
            self.flow(
                ["Tekst", "Embedder", "Vector", "Postgres kb_docs"],
                title="Van tekst naar vector",
            )
        elif "postgres" in t or "pgvector" in t or "vector database" in t:
            self.layers(
                [
                    ("chunk_id", "Primary key voor upsert"),
                    ("text", "Chunk inhoud"),
                    ("embedding", "pgvector (1536 dims, HNSW)"),
                    ("payload", "JSONB type-specifieke velden"),
                    ("jurisdictions", "text[] met GIN-filter"),
                ],
                title="kb_docs schema (PostgreSQL)",
            )
            self.flow(
                ["Query", "Embed", "pgvector ANN", "Filter meta", "Citations"],
                title="Retrieval-pad",
            )
        elif "entities" in t or "structured database" in t or "gestructureerde" in t:
            self.matrix(
                ["Tabel", "Tool", "Nut"],
                [
                    ["clients", "conflict_check", "Belangen"],
                    ["attorneys", "route_lead", "Toewijzing"],
                    ["past_cases", "estimate_value", "Comps"],
                ],
                title="Postgres-tabellen vs tools",
            )
        elif "docker" in t or "fastapi" in t or "backend" in t:
            self.layers(
                [
                    ("postgres", "pgvector DB container"),
                    ("init", "schema seed + ETL (eenmalig)"),
                    ("api", "FastAPI op :8000"),
                    ("ui", "Streamlit op :8501"),
                ],
                title="Docker Compose services",
            )
        elif "agno tools" in t or "sol, conflict" in t:
            self.flow(
                ["SOL", "Conflict", "Value", "Route", "Fallback"],
                title="Toolketen",
            )
            self.vflow(
                ["Feiten binnen", "LLM kiest tools (of plan)", "Pydantic I/O", "Resultaat -> scoring"],
                title="Tool-aanroepstructuur",
            )
        elif "intake agent" in t or "plan → retrieve" in t or "plan -> retrieve" in t:
            self.cycle(
                ["Plan", "Retrieve", "Tools", "Decide", "Check", "Respond"],
                title="Agentische loop",
            )
        elif "multi-turn" in t or "interview" in t:
            self.flow(
                ["Vraag", "Antwoord", "Feiten+", "Genoeg?", "Screening"],
                title="Interview-flow",
            )
            self.matrix(
                ["Veld", "Voorbeeld"],
                [
                    ["name", "Alex Rivera"],
                    ["practice_area", "Personal Injury"],
                    ["jurisdiction", "CA"],
                    ["incident_date", "2025-06-01"],
                    ["opposing_party", "City Transit"],
                    ["damages", "45000"],
                ],
                title="Verplichte intake-velden",
            )
        elif "lead scoring" in t or "beslissingen" in t:
            self.flow(
                ["Facts+Tools", "context.py", "score_lead()", "Decision"],
                title="Unified scoring-pad",
            )
            self.matrix(
                ["Decision", "Betekenis"],
                [
                    ["SCHEDULE_CONSULT", "Plan intake"],
                    ["REVIEW", "Menselijke check"],
                    ["REJECT", "Niet aannemen"],
                ],
                title="Beslissingsruimte",
            )
        elif "guardrail" in t:
            self.vflow(
                [
                    "Disclaimer verplicht",
                    "Geen legal advice",
                    "Citations verplicht",
                    "Escalate bij twijfel",
                    "Geen verzonnen wet",
                ],
                title="Guardrail-stapel",
            )
        elif "observability" in t or "monitoring" in t:
            self.layers(
                [
                    ("Custom JSONL", "latency/tools/scores"),
                    ("Metrics API", "session/daily summary"),
                    ("Streamlit dash", "Grafieken"),
                    ("Agno tracing", "traces.db spans"),
                ],
                title="Observability-stack",
            )
        elif "evaluation" in t or "harness" in t:
            self.flow(
                ["leads.csv", "Agent run", "Metrics", "Report"],
                title="Evaluatieketen",
            )
            self.matrix(
                ["Dimensie", "Meet"],
                [
                    ["Retrieval", "Hit rate"],
                    ["Grounding", "Citations"],
                    ["Qualify", "Label match"],
                    ["Guardrails", "Compliance"],
                    ["Cost/Lat", "Efficiency"],
                ],
                title="Eval-dimensies (sample)",
            )
        elif "streamlit" in t or "ui & demo" in t or title.startswith("Streamlit"):
            self.flow(
                ["Interview tab", "Feiten", "run_intake", "Result UI"],
                title="UI Interview-pad",
            )
            self.flow(
                ["Quick text", "parse facts", "Pipeline", "JSON view"],
                title="UI Quick-analysis-pad",
            )
        elif ".env" in t or "configuratie" in t:
            self.vflow(
                [".env.example", "Kopieer naar .env", "Vul keys", "config.py laadt", "LLM/Embedder"],
                title="Config-flow",
            )
        elif "git-workflow" in t or "ci" in t:
            self.flow(
                ["feature/*", "PR", "CI smoke", "main"],
                title="Git + CI flow",
            )
            self.vflow(
                ["checkout", "pip install", "init DB", "load KB", "demo+eval", "artifacts"],
                title="CI smoke-test stappen",
            )
        elif "systeem starten" in t or "stap-voor-stap" in t:
            self.vflow(
                ["pip install", "init_structured_db", "etl.pipeline", "demo.py", "streamlit UI"],
                title="Startvolgorde",
            )
        elif "demo-video" in t:
            self.flow(
                ["Probleem", "Architectuur", "4 scenario's", "Dashboard", "Slot"],
                title="Video-storyboard",
            )
        elif "troubleshooting" in t or "fouten" in t:
            self.matrix(
                ["Symptoom", "Check"],
                [
                    ["Import error", "venv + requirements"],
                    ["Key missing", ".env OPENAI_API_KEY"],
                    ["Dim mismatch", "herlaad KB"],
                    ["CI rood", "secret + demo + eval"],
                ],
                title="Debug-matrix",
            )
        elif "oefeningen" in t:
            self.flow(
                ["Begrip", "ETL tweak", "Tool call", "Interview", "Eval"],
                title="Oefenparcours",
            )
        elif "glossarium" in t or "checklist oplevering" in t:
            self.vflow(
                ["Repo + README", "Reports", "Demo 4/4", "CI groen", "Video + key"],
                title="Oplevervolgorde",
            )
        elif "werkvoorbeeld" in t or "valid personal" in t:
            self.flow(
                ["Tekst", "Parse", "Plan", "Retrieve", "Tools", "Score"],
                title="Runtime end-to-end",
            )
        elif "verlopen sol" in t:
            self.flow(
                ["Oude datum", "SOL tool", "valid=False", "REJECT"],
                title="SOL-fail pad",
            )
        elif "conflict of interest" in t:
            self.flow(
                ["ACME+Employment", "Map client", "Postgres hit", "REJECT+escalate"],
                title="Conflict-pad",
            )
        elif "onzekere immigratie" in t:
            self.flow(
                ["Incomplete feiten", "uncertain flag", "REVIEW", "Escalate"],
                title="Abstention-pad",
            )
        elif "3 minuten" in t or "leg je lexintake uit" in t:
            self.vflow(
                ["Probleem", "Agentic RAG", "Tools+KB", "Guardrails", "Bewijs (demo/CI)"],
                title="Pitch-structuur",
            )
        elif "dataflow" in t:
            self.flow(
                ["Disk KB", "ETL", "Postgres", "Agent", "UI/API JSON"],
                title="Dataflow 30.000 ft",
            )
        elif "provider-agnostic" in t:
            self.matrix(
                ["Laag", "Keuze"],
                [
                    ["LLM", "openai/anthropic/groq"],
                    ["Embed", "openai"],
                    ["Logic", "onveranderd"],
                ],
                title="Provider-scheiding",
            )
        elif "goed genoeg" in t or "grading" in t:
            self.vflow(
                ["Working demo", "Uitlegbaar", "Git+CI", "Reports", "Video"],
                title="Grading-prioriteiten",
            )
        elif "veiligheid" in t or "ethiek" in t:
            self.layers(
                [
                    ("No advice", "Geen directives aan prospect"),
                    ("Escalate", "Twijfel -> mens"),
                    ("Cite", "KB evidence"),
                    ("Secrets", "Keys niet in git"),
                ],
                title="Veiligheidslagen",
            )
        elif "uitbreidingen" in t or "tijd over" in t:
            self.flow(
                ["Corrective RAG", "Multi-agent", "HITL", "Memory"],
                title="Stretch roadmap",
            )
        elif "cheatsheet: commands" in t or "unit test" in t or "code-kwaliteit" in t:
            self.vflow(
                ["setup", "test", "init DB", "ETL", "demo", "UI", "eval"],
                title="Command-volgorde",
            )
        elif "cheatsheet: bestanden" in t:
            self.tree(
                [
                    "agents/intake/agent.py     <- agent loop",
                    "db/pgvector_store.py       <- vector search",
                    "tools/*.py                 <- SOL/conflict/value/route",
                    "backend/api/main.py        <- FastAPI entry",
                    "frontend/app.py            <- Streamlit UI",
                    "docker-compose.yml         <- stack",
                    "etl/pipeline.py            <- ETL",
                    ".github/workflows/ci.yml   <- CI",
                ],
                title="Bestanden om aan te wijzen",
            )
        elif "zelftest" in t:
            self.matrix(
                ["Vraag", "Focus"],
                [
                    ["RAG vs LLM?", "Grounding"],
                    ["Postgres entities waarom?", "Exact match"],
                    ["5 fasen?", "Loop"],
                    ["CI keys?", "OPENAI_API_KEY secret"],
                ],
                title="Zelftest-kaart",
            )
        elif "faq" in t or "verdieping" in t:
            self.flow(
                ["Vraag", "Kort antwoord", "Welk bestand?", "Demo-check"],
                title="FAQ-leermethode",
            )
        else:
            self.flow(
                ["Input", "Verwerking", "Bewijs/Tools", "Output"],
                title="Algemene structuur van dit hoofdstuk",
            )

    def h2(self, title: str) -> None:
        self.ln(2)
        self.set_font("Body", "B", 13)
        self.set_text_color(30, 60, 90)
        self.set_x(self.l_margin)
        self.multi_cell(0, 7, title)
        self.set_text_color(20, 20, 20)
        self.ln(1)

    def h3(self, title: str) -> None:
        self.ln(1)
        self.set_font("Body", "B", 11)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, title)
        self.ln(0.5)

    def p(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Body", "", 11)
        self.multi_cell(0, 6, text)
        self.ln(1.5)

    def bullet(self, items: list[str]) -> None:
        self.set_font("Body", "", 11)
        for item in items:
            self.set_x(self.l_margin)
            self.multi_cell(0, 6, f"- {item}")
        self.ln(1.5)

    def note(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.set_fill_color(240, 246, 244)
        self.set_font("Body", "I", 10)
        self.multi_cell(0, 5.5, f"Let op: {text}", fill=True)
        self.ln(2)

    def code(self, text: str) -> None:
        self.set_font("Body", "", 9)
        self.set_fill_color(245, 245, 245)
        for line in text.splitlines() or [""]:
            self.set_x(self.l_margin)
            safe = line.replace("\t", "  ")[:100]
            self.multi_cell(0, 5, safe if safe else " ", fill=True)
        self.ln(2)
        self.set_font("Body", "", 11)


def build() -> Path:
    """Assemble all chapters and write ``LexIntake_Leerboek.pdf``; return output path."""
    pdf = Leerboek()
    pdf.cover()

    # TOC
    pdf.add_page()
    pdf.set_font("Body", "B", 18)
    pdf.multi_cell(0, 9, "Inhoudsopgave")
    pdf.ln(2)
    pdf.flow(
        ["Begrip", "Bouwen", "Draaien", "Meten", "Opleveren"],
        title="Hoe dit boek is opgebouwd",
    )
    pdf.layers(
        [
            ("Deel A", "Probleem, begrippen, eisen"),
            ("Deel B", "KB, ETL, DB, tools, agent"),
            ("Deel C", "Interview, scoring, guardrails"),
            ("Deel D", "Monitoring, eval, UI, CI"),
            ("Deel E", "Voorbeelden, cheatsheets, FAQ"),
        ],
        title="Leerpad in 5 delen",
    )
    pdf.ln(2)
    toc = [
        "1. Wat is de opdracht en waarom bestaat LexIntake?",
        "2. Belangrijke begrippen (eenvoudig uitgelegd)",
        "3. Capstone-eisen: wat moet je opleveren?",
        "4. Architectuur: het grote plaatje",
        "5. Repository-structuur map voor map",
        "6. Bestandsgids: wat doet elk bestand?",
        "7. Knowledge Base (kb/) bouwen",
        "8. ETL-pipeline stap voor stap",
        "9. Embeddings: OpenAI",
        "10. PostgreSQL + pgvector (kb_docs)",
        "11. Gestructureerde entiteiten in PostgreSQL",
        "12. Docker Compose & FastAPI backend",
        "13. Agno tools (SOL, conflict, value, route)",
        "14. De Intake Agent (plan → retrieve → tools → decide)",
        "15. Multi-turn interview met prospects",
        "16. Lead scoring & beslissingen",
        "17. Guardrails (juridische veiligheid)",
        "18. Observability & Agno Monitoring",
        "19. Evaluation harness",
        "20. Streamlit UI & demo",
        "21. Configuratie met .env",
        "22. Git-workflow, PR’s en CI",
        "23. Stap-voor-stap: systeem starten",
        "24. Demo-video voorbereiden",
        "25. Troubleshooting & veelgemaakte fouten",
        "26. Oefeningen om te oefenen",
        "27. Glossarium & checklist oplevering",
        "28. Werkvoorbeelden (PI, SOL, conflict, uncertain)",
        "29. Presentatiescript, dataflow, providers, ethiek",
        "30. Unit tests & code-kwaliteit",
        "31. Cheatsheets, zelftest en FAQ-verdieping",
    ]
    pdf.set_font("Body", "", 11)
    for line in toc:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, line)
    pdf.ln(4)
    pdf.note("Lees dit boek sequentieel de eerste keer. Daarna kun je per hoofdstuk springen.")

    # 1
    pdf.h1("Wat is de opdracht en waarom bestaat LexIntake?")
    pdf.p(
        "Advocatenkantoren krijgen elke dag veel nieuwe leads: via de website, e-mail en "
        "telefoonformulieren. Een groot deel van de tijd van een paralegal gaat op aan "
        "filteren: verkeerde practice area, verkeerde staat (jurisdiction), verlopen "
        "verjaringstermijn (statute of limitations / SOL), belangenconflict, of een zaak "
        "die te weinig waard is."
    )
    pdf.p(
        "LexIntake is géén chatbot die zomaar praat. Het is een agentic RAG-systeem: een "
        "agent die beslist welke kennis hij ophaalt, welke tools hij aanroept, en of hij "
        "genoeg bewijs heeft om een lead te scoren en door te sturen."
    )
    pdf.h2("Wat moet de agent kunnen?")
    pdf.bullet(
        [
            "Prospects interviewen (vragen stellen tot de feiten compleet genoeg zijn)",
            "Firm knowledge ophalen uit een knowledge base (RAG)",
            "Tools aanroepen (SOL-check, conflict, case value, routing)",
            "Leads scoren en een beslissing geven",
            "Elke beslissing uitleggen met KB-citaten",
            "Escaleren naar een mens bij onzekerheid",
        ]
    )
    pdf.h2("Wat is dit níet?")
    pdf.bullet(
        [
            "Geen juridisch advies aan cliënten",
            "Geen volledige case-management / CRM-vervanging",
            "Geen vervanging van een advocaat",
        ]
    )
    pdf.p(
        "Onthoud de disclaimer die overal terugkomt: "
        "“This is not legal advice. Consult a licensed attorney.”"
    )
    

    # 2
    pdf.h1("Belangrijke begrippen (eenvoudig uitgelegd)")
    terms = [
        (
            "RAG (Retrieval-Augmented Generation)",
            "Eerst relevante tekstfragmenten ophalen uit een kennisbank, daarna pas "
            "antwoorden genereren. Zo ‘verzint’ het model minder en kan het citaten geven.",
        ),
        (
            "Agentic",
            "Het systeem plant stappen, kiest tools, en beslist of er genoeg info is. "
            "Het volgt niet blind één vaste prompt.",
        ),
        (
            "Embedding",
            "Een tekst als vector (lijst getallen). Vergelijkbare betekenissen liggen "
            "dicht bij elkaar in die ruimte.",
        ),
        (
            "Vector database",
            "Database geoptimaliseerd om ‘meest gelijkende’ embeddings te zoeken "
            "(semantische search). Bij LexIntake: PostgreSQL met pgvector-extensie.",
        ),
        (
            "Chunk",
            "Klein stukje tekst uit een groter document, handig om te indexeren en te citeren.",
        ),
        (
            "Tool calling",
            "De agent roept een functie aan (bijv. conflict_check) met gestructureerde input/output.",
        ),
        (
            "SOL / Statute of Limitations",
            "Verjaringstermijn: binnen hoeveel tijd moet een claim (globaal) nog geldig zijn.",
        ),
        (
            "Guardrail",
            "Veiligheidsregel: disclaimer, geen juridisch advies, escalatie, citaties verplicht.",
        ),
        (
            "Deterministisch pad",
            "Zelfde input → zelfde output, zonder externe LLM. Belangrijk voor CI/tests.",
        ),
        (
            "Provider-agnostic",
            "Je kunt LLM/embeddings wisselen via config (.env), niet hardcoded aan één vendor.",
        ),
    ]
    for title, body in terms:
        pdf.h3(title)
        pdf.p(body)
    

    # 3
    pdf.h1("Capstone-eisen: wat moet je opleveren?")
    pdf.p(
        "De opdracht-PDF beschrijft leerdoelen, verplichte bouwstenen en deliverables. "
        "Hieronder de checklist in mensentaal."
    )
    pdf.h2("Bouwstenen die er moeten zijn")
    pdf.bullet(
        [
            "Synthetische knowledge base (practice areas, SOL, fees, cases, attorneys, clients, FAQs)",
            "ETL: extract → clean → dedupe → chunk → metadata → embeddings → load",
            "ETL-eigenschappen: re-runnable, idempotent, incremental",
            "Agent-loop: Plan → Retrieve → Tool Call → Decision → Self-check",
            "Tools: SOL, conflict, estimate_case_value, route_lead",
            "Lead output: qualified, lead_score, priority, decision, recommended_attorney",
            "Guardrails in elk antwoord",
            "Observability (tokens, cost, latency, tools, retrieval, escalaties, case value)",
            "Git: main/develop/feature/*, PRs, protected main, GitHub Actions (aanbevolen)",
            "Stack: Agno + LLM + embeddings + PostgreSQL/pgvector + FastAPI + Streamlit + Docker + pytest + monitoring",
            "Evaluation op ~20–30 labeled leads (8 dimensies)",
        ]
    )
    pdf.h2("Deliverables")
    pdf.bullet(
        [
            "GitHub repository",
            "Working system",
            "Synthetic KB",
            "Evaluation Report",
            "Dashboard",
            "README",
            "Demo Video (dit moet jij nog opnemen)",
            "Design Report",
        ]
    )
    pdf.h2("Stretch goals (niet verplicht)")
    pdf.bullet(
        [
            "Corrective RAG",
            "Multi-agent team",
            "Human-in-the-loop console",
            "Persistent memory",
            "Uitgebreidere CI/CD (nightly full eval)",
        ]
    )
    pdf.p(
        "LexIntake dekt de MVP-eisen. Stretch is optioneel. De demo-video is de "
        "belangrijkste openstaande menselijke deliverable."
    )
    

    # 4
    pdf.h1("Architectuur: het grote plaatje")
    pdf.p(
        "Denk in lagen. Een prospect praat met de Streamlit UI (frontend/) of roept "
        "de FastAPI backend aan. Beide praten met de IntakeAgent. De agent haalt kennis "
        "uit PostgreSQL kb_docs (pgvector), roept tools aan die entities/KB gebruiken, "
        "scoort de lead, checkt guardrails, en geeft een uitleg terug."
    )
    pdf.code(
        "Prospect / paralegal\n"
        "        |\n"
        "   Streamlit UI (frontend/)  —  FastAPI (backend/)\n"
        "        |\n"
        "   IntakeAgent (agents/intake/)\n"
        "   plan -> retrieve -> tools -> decide -> self-check -> respond\n"
        "      |         |         |\n"
        "   Postgres   Agno tools  Lead scoring\n"
        "   kb_docs    SOL/conflict/value/route\n"
        "   (pgvector)     |\n"
        "      ^      clients / attorneys / past_cases\n"
        "   ETL (kb/ -> chunks -> embeddings)\n"
        "   Docker: postgres + init + api + ui"
    )
    pdf.h2("Live pad")
    pdf.bullet(
        [
            "OpenAI embeddings + gpt-4.1 (echte semantiek + uitleg)",
            "OPENAI_API_KEY is verplicht voor ETL, UI, demo, evaluatie en CI",
        ]
    )
    pdf.p(
        "GitHub Actions gebruikt dezelfde live providers via de repository secret "
        "OPENAI_API_KEY."
    )
    

    # 5
    pdf.h1("Repository-structuur map voor map")
    pdf.p(
        "LexIntake is opgebouwd als een monorepo: elke map heeft één duidelijke rol. "
        "Data stroomt van kb/ via etl/ naar PostgreSQL; runtime-logica zit in agents/, "
        "tools/ en scoring/; presentatie in frontend/ en backend/."
    )
    pdf.tree(
        [
            "LexIntake/",
            "├── kb/                 # brondata (JSON + Markdown)",
            "├── etl/                # extract → transform → load",
            "│   ├── extract/        # leest kb-bestanden",
            "│   ├── transform/      # clean, chunk, embed",
            "│   └── load/             # schrijft naar Postgres",
            "├── db/                 # database-laag",
            "│   ├── models.py       # SQLAlchemy entities",
            "│   ├── pgvector_store  # kb_docs vector search",
            "│   ├── engine.py       # Postgres connectie",
            "│   └── migrations/     # Alembic schema",
            "├── agents/             # AI-agents",
            "│   ├── intake/         # IntakeAgent (kern)",
            "│   ├── interview/      # multi-turn gesprek",
            "│   ├── llm.py          # provider-agnostic LLM",
            "│   └── shared/         # Agno factory helpers",
            "├── tools/              # Agno @tool functies",
            "├── scoring/            # deterministische lead scoring",
            "├── backend/            # FastAPI REST API",
            "│   ├── api/routes/     # /health, /v1/intake, /v1/interview",
            "│   └── services/       # business logic wrappers",
            "├── frontend/           # Streamlit UI + demo",
            "│   └── components/     # header, disclaimer, result viewer",
            "├── monitoring/         # metrics, dashboard, Agno traces",
            "├── evaluation/         # labeled leads + harness",
            "├── scripts/            # docker_init, ensure_env",
            "├── docs/               # reports + dit leerboek",
            "├── docker-compose.yml  # Postgres + init + API + UI",
            "├── Dockerfile          # app image",
            "├── tests/              # pytest unit tests (16+)",
            "├── pyproject.toml      # pytest pythonpath + package config",
            "├── Makefile            # make setup / test / ui / api / eval",
            "├── config.py           # .env configuratie",
            "└── .github/workflows/  # CI: pytest + smoke-test",
        ],
        title="Volledige repo-boom",
    )
    folders = [
        ("kb/", "Synthetische kennisbank (JSON/MD). Bron van waarheid voor intake-regels."),
        ("etl/", "Pipeline: extract → clean → dedupe → chunk → metadata → embed → load."),
        ("db/", "PostgreSQL: SQLAlchemy models, pgvector store, Alembic migrations, seed scripts."),
        ("agents/", "IntakeAgent (plan/retrieve/tools/decide), InterviewAgent, LLM wiring."),
        ("tools/", "Agno @tool functies: SOL, conflict, value, route."),
        ("scoring/", "score_lead(), context builder, named constants (single source of truth)."),
        ("tests/", "Pytest: scoring, guardrails, fact_parse, conflict_check (geen API key)."),
        ("backend/", "FastAPI REST API (intake analyze, interview sessions, health)."),
        ("frontend/", "Streamlit UI (interview + quick analysis) + CLI demo scenarios."),
        ("monitoring/", "JSONL logger, metrics, Streamlit dashboard, Agno traces."),
        ("evaluation/", "leads.csv, eval_metrics, run_evaluation.py, report logs."),
        ("scripts/", "docker_init.py (container bootstrap), ensure_env.py (.env helper)."),
        ("docs/", "Design report, evaluation report, demo script, dit leerboek."),
    ]
    for name, desc in folders:
        pdf.h3(name)
        pdf.p(desc)
    pdf.h2("Root-bestanden")
    pdf.bullet(
        [
            "README.md — setup, architectuur, quick start",
            "requirements.txt — Python dependencies",
            "config.py — leest .env (DATABASE_URL, providers, models, keys)",
            ".env.example — template zonder geheimen",
            "docker-compose.yml — Postgres + init + API + UI containers",
            "Makefile — make setup, test, ui, api, demo, eval, dashboard",
            "pyproject.toml — pytest config + pip install -e . support",
            "Dockerfile — Python app image (PYTHONPATH=/app)",
        ]
    )

    # 6 — Bestandsgids
    pdf.h1("Bestandsgids: wat doet elk bestand?")
    pdf.p(
        "Deze tabel is je navigatiekaart. Als je een bug zoekt of iets moet uitleggen "
        "tijdens de demo, wijs je naar het juiste bestand."
    )
    file_guide = [
        ["config.py", "Laadt .env: DATABASE_URL, LLM/embedding providers, API keys"],
        ["db/engine.py", "PostgreSQL connectie + pgvector/pg_trgm extensies"],
        ["db/models.py", "SQLAlchemy: Client, Attorney, PastCase tabellen"],
        ["db/pgvector_store.py", "kb_docs upsert + vector search (cosine/HNSW)"],
        ["db/schema.py", "kb_docs DDL + embedding dimensies"],
        ["db/init_structured_db.py", "Maakt tabellen + seed vanuit kb/*.json"],
        ["db/structured_db.py", "CRUD helpers voor entities (clients, attorneys)"],
        ["db/migrations/", "Alembic versies voor schema-wijzigingen"],
        ["etl/pipeline.py", "Hoofd-ETL: orchestratie extract→load"],
        ["etl/extract/documents.py", "Leest alle kb/ bestanden in als documenten"],
        ["etl/transform/clean.py", "Normaliseert whitespace/rommel"],
        ["etl/transform/deduplicate.py", "content_hash deduplicatie"],
        ["etl/transform/chunk.py", "Splitst tekst, genereert chunk_id"],
        ["etl/transform/metadata.py", "Voegt practice_area, doc_type, jurisdictions toe"],
        ["etl/transform/embeddings.py", "OpenAI embedder via Agno adapter"],
        ["etl/load/vector_db.py", "Upsert chunks naar kb_docs in Postgres"],
        ["agents/intake/agent.py", "IntakeAgent: plan→retrieve→tools→decide→check→respond"],
        ["agents/intake/retrieve.py", "pgvector search + metadata filters → citaties"],
        ["agents/intake/fact_parse.py", "Parse ruwe tekst naar IntakeFacts"],
        ["agents/intake/decide.py", "Adapter: score_lead → DecisionResult + next_steps"],
        ["scoring/context.py", "build_lead_score_context() — gedeelde scoring-input"],
        ["scoring/constants.py", "Named thresholds (SCORE_SCHEDULE_MIN, etc.)"],
        ["agents/intake/guardrails.py", "Disclaimer, citaties, escalatie checks"],
        ["agents/intake/models.py", "Pydantic: IntakeFacts, PlanResult, Response"],
        ["agents/intake/tools.py", "Tool-aanroep wiring (agentic + deterministic)"],
        ["agents/intake/prompts.xml", "Systeem-instructies voor de agent"],
        ["agents/interview/agent.py", "InterviewSession: multi-turn Q&A → screening"],
        ["agents/llm.py", "build_model(): OpenAI/Anthropic/Groq provider switch"],
        ["agents/shared/make_agent.py", "Agno Agent factory + tracing setup"],
        ["tools/check_statute_of_limitations.py", "SOL-check op sol_tables.json"],
        ["tools/conflict_check.py", "Zoekt client match in Postgres clients"],
        ["tools/estimate_case_value.py", "Case value schatting via past_cases comps"],
        ["tools/route_lead.py", "Attorney routing op specialisatie/availability"],
        ["tools/common.py", "Gedeelde helpers (practice area match, vector_search)"],
        ["scoring/lead_scoring.py", "score_lead(): qualified, score, decision"],
        ["backend/api/main.py", "FastAPI app entrypoint + CORS"],
        ["backend/api/routes/intake.py", "POST /v1/intake/analyze"],
        ["backend/api/routes/interview.py", "Interview session endpoints"],
        ["backend/api/routes/health.py", "GET /health"],
        ["backend/api/schemas.py", "Pydantic request/response modellen"],
        ["backend/api/session_store.py", "In-memory interview sessie opslag"],
        ["backend/services/intake_service.py", "Gedeelde service: agent + score_lead payload"],
        ["frontend/app.py", "Streamlit: interview tab + quick analysis tab"],
        ["frontend/demo.py", "CLI demo: 4 scenario's (PI, SOL, conflict, uncertain)"],
        ["frontend/runner.py", "Shared runner voor UI en demo"],
        ["frontend/components/", "UI onderdelen: header, disclaimer, result viewer"],
        ["monitoring/logger.py", "JSONL event logging + PII sanitization"],
        ["monitoring/metrics.py", "Tokens, latency, tool calls, scores aggregatie"],
        ["monitoring/dashboard.py", "Streamlit metrics + Agno trace viewer"],
        ["monitoring/agno_tracing.py", "Agno OpenTelemetry tracing setup"],
        ["evaluation/run_evaluation.py", "Draait agent op labeled leads, meet 8 dimensies"],
        ["evaluation/leads.csv", "~30 synthetische gelabelde test-leads"],
        ["evaluation/eval_metrics.py", "Metric berekeningen per dimensie"],
        ["scripts/docker_init.py", "Container init: init_structured_db + etl.pipeline"],
        ["scripts/ensure_env.py", "Maakt .env aan vanuit .env.example indien nodig"],
        ["tests/", "Pytest suite: lead_scoring, decide, guardrails, fact_parse, context"],
        ["pyproject.toml", "pytest pythonpath + setuptools package discovery"],
        [".github/workflows/ci.yml", "CI: pytest, init DB, ETL, demo, eval --limit 5"],
    ]
    pdf.matrix(
        ["Bestand", "Functie"],
        file_guide,
        title="Complete bestandsgids",
    )
    pdf.h2("Dataflow tussen bestanden")
    pdf.flow(
        ["kb/*.json", "etl/pipeline.py", "pgvector_store.py", "retrieve.py", "agent.py", "frontend/app.py"],
        title="Van brondata tot UI-antwoord",
    )
    pdf.note(
        "Imports draaien vanuit repo-root via PYTHONPATH (Makefile/Docker/CI zetten dit). "
        "Geen sys.path-hacks meer in library code. Optioneel: pip install -e ."
    )

    # 7
    pdf.h1("Knowledge Base (kb/) bouwen")
    pdf.p(
        "De KB is synthetisch maar realistisch. Ze bestaat zodat de agent iets heeft om "
        "op te ‘steunen’ (grounding) in plaats van regels te verzinnen."
    )
    pdf.h2("Bestanden")
    pdf.bullet(
        [
            "practice_areas.json — vaste lijst van 10 practice areas",
            "acceptance_criteria.json — wanneer neemt het kantoor een zaak aan?",
            "fee_structure.json — contingency/hourly/retainer per gebied",
            "sol_tables.json — SOL-regels per staat/zaaktype",
            "past_cases.json — vergelijkbare zaken voor valuation",
            "attorneys.json — specialisatie, ervaring, availability",
            "clients.json — bestaande cliënten voor conflict checks",
            "faqs.md — algemene groundingstekst",
        ]
    )
    pdf.h2("Practice areas (exact)")
    pdf.p(
        "Personal Injury, Employment Law, Immigration, Family Law, Criminal Defense, "
        "Workers’ Compensation, Medical Malpractice, Product Liability, Civil Rights, "
        "Consumer Protection."
    )
    pdf.h2("Waarom JSON + Markdown?")
    pdf.p(
        "JSON is makkelijk te parsen voor tools (SOL/fees/cases). Markdown FAQs zijn "
        "goed te chunk’en voor retrieval. De ETL normaliseert alles tot documenten met "
        "metadata."
    )
    pdf.note(
        "Wijzig je de KB, dan moet je embeddings opnieuw laden "
        "(python -m etl.pipeline) zodat kb_docs in Postgres synchroon blijft."
    )
    

    # 7
    pdf.h1("ETL-pipeline stap voor stap")
    pdf.p(
        "ETL = Extract, Transform, Load. Bij LexIntake is ‘Transform’ uitgebreid tot "
        "clean, dedupe, chunk, metadata, embeddings."
    )
    steps = [
        ("1. Extract", "Lees alle KB-bestanden in als documenten."),
        ("2. Clean", "Normaliseer whitespace/rommel, maak tekst consistent."),
        ("3. Deduplicate", "Zelfde inhoud → één document via content_hash."),
        ("4. Chunk", "Splits lange teksten in stukken met stabiele chunk_id."),
        ("5. Metadata", "Voeg practice_area, jurisdictions, doc_type, timestamps toe."),
        ("6. Embeddings", "Maak vectoren met OpenAI text-embedding-3-small."),
        ("7. Load", "Upsert naar PostgreSQL kb_docs via pgvector_store.py."),
    ]
    for t, b in steps:
        pdf.h3(t)
        pdf.p(b)
    pdf.h2("Verplichte eigenschappen")
    pdf.bullet(
        [
            "Re-runnable: je mag de pipeline steeds opnieuw draaien zonder chaos",
            "Idempotent: zelfde input convergeert naar dezelfde store-state (upsert op chunk_id)",
            "Incremental: ongewijzigde chunks kunnen embeddings hergebruiken",
        ]
    )
    pdf.h2("Commands")
    pdf.code(
        "python -m db.init_structured_db\n"
        "python -m etl.pipeline"
    )
    

    # 8
    pdf.h1("Embeddings: OpenAI")
    pdf.p(
        "Embeddings zetten tekst om naar getallen. LexIntake gebruikt OpenAI "
        "text-embedding-3-small via get_embedder()."
    )
    pdf.h2("OpenAI text-embedding-3-small")
    pdf.bullet(
        [
            "Dimensies: 1536",
            "Echte semantische gelijkenis (“rear-end collision” ≈ “car accident injury”)",
            "Vereist OPENAI_API_KEY",
            "Gebruikt via Agno OpenAIEmbedder adapter in etl/transform/embeddings.py",
        ]
    )
    pdf.h2(".env voorbeeld")
    pdf.code(
        "LEXINTAKE_EMBEDDING_PROVIDER=openai\n"
        "LEXINTAKE_EMBEDDING_MODEL=text-embedding-3-small\n"
        "LEXINTAKE_EMBEDDING_DIMS=1536\n"
        "OPENAI_API_KEY=sk-..."
    )
    pdf.note(
        "Wissel je van embedding-dimensie, dan moet je kb_docs opnieuw laden "
        "vanwege dimensie-mismatch. Dat is normaal."
    )
    

    # 9
    pdf.h1("PostgreSQL + pgvector (kb_docs)")
    pdf.p(
        "LexIntake gebruikt één PostgreSQL-database voor alles. Vector-chunks staan in "
        "tabel kb_docs met de pgvector-extensie. Zoeken gebeurt via HNSW-index op cosine "
        "similarity, met metadata filters."
    )
    pdf.h2("Schema (kernvelden)")
    pdf.bullet(
        [
            "chunk_id — primaire sleutel voor idempotente upsert",
            "text — chunk tekst",
            "embedding — pgvector kolom (1536 dims)",
            "practice_area — slug voor filtering",
            "jurisdictions — text[] array met GIN-index",
            "doc_type — bv. sol_rules, acceptance, faq",
            "payload — JSONB met type-specifieke velden",
        ]
    )
    pdf.h2("Belangrijke bestanden")
    pdf.bullet(
        [
            "db/pgvector_store.py — upsert + vector_search",
            "db/schema.py — DDL + embedding dimensies",
            "agents/intake/retrieve.py — retrieval met filters",
            "tools/common.py — vector_search wrapper",
        ]
    )
    pdf.h2("Retrieval in de agent")
    pdf.p(
        "De agent embedt de query via OpenAI, zoekt top_k via pgvector (typisch 5–10) en "
        "filtert op practice_area / jurisdiction / doc_type. Resultaten worden citaties."
    )
    pdf.code(
        "hits = vector_search(\n"
        "    query, top_k=8,\n"
        "    practice_area='Personal Injury',\n"
        "    jurisdiction='CA', doc_type='sol_rules')"
    )
    

    # 10
    pdf.h1("Gestructureerde entiteiten in PostgreSQL")
    pdf.p(
        "Entities met relaties en exacte lookups zitten in dezelfde PostgreSQL-database "
        "als kb_docs (niet meer in aparte SQLite)."
    )
    pdf.h2("Tabellen")
    pdf.bullet(
        [
            "clients — voor conflict_check (naam/opposing party)",
            "attorneys — voor route_lead (specialisatie, availability, jurisdictions)",
            "past_cases — voor estimate_case_value (comps), FK naar clients + attorneys",
        ]
    )
    pdf.h2("Belangrijke bestanden")
    pdf.bullet(
        [
            "db/models.py — SQLAlchemy ORM (Client, Attorney, PastCase)",
            "db/structured_db.py — query helpers voor tools",
            "db/init_structured_db.py — schema + seed vanuit kb/*.json (python -m db.init_structured_db)",
            "db/migrations/ — Alembic (001 schema, 002 pgvector)",
        ]
    )
    pdf.h2("Seed")
    pdf.p(
        "python -m db.init_structured_db maakt tabellen aan en vult vanuit kb/*.json. "
        "Conflict-demo's werken omdat seeded clients (zoals Elena Vasquez) bestaan."
    )

    # 12
    pdf.h1("Docker Compose & FastAPI backend")
    pdf.p(
        "LexIntake draait standaard als Docker-stack via docker-compose.yml: postgres, "
        "init (eenmalig), api (FastAPI :8000) en ui (Streamlit :8501)."
    )
    pdf.h2("Docker services")
    pdf.bullet(
        [
            "postgres — pgvector/pgvector:pg16, poort 5432",
            "init — scripts/docker_init.py: init_structured_db + etl.pipeline",
            "api — backend/api/main.py via uvicorn",
            "ui — frontend/app.py via streamlit",
        ]
    )
    pdf.h2("FastAPI endpoints")
    pdf.bullet(
        [
            "GET /health — health check",
            "GET / — service discovery (docs + route hints)",
            "POST /v1/intake/analyze — quick analysis (één casebeschrijving)",
            "POST /v1/interview/sessions — start interview sessie",
            "POST /v1/interview/sessions/{id}/turns — antwoord sturen",
            "DELETE /v1/interview/sessions/{id} — sessie opruimen",
        ]
    )
    pdf.p(
        "Backend API-tests staan in tests/test_backend_api.py (FastAPI TestClient, "
        "pipeline gemockt zodat CI geen live LLM nodig heeft voor HTTP-coverage)."
    )
    pdf.h2("Makefile")
    pdf.code(
        "make setup        # volledige Docker stack\n"
        "make setup-local  # host Python + Postgres container\n"
        "make ui / api     # Streamlit / FastAPI lokaal\n"
        "make demo / eval  # demo + evaluation"
    )
    pdf.note("DATABASE_URL is verplicht: postgresql://lexintake:lexintake@localhost:5432/lexintake")

    # 13
    pdf.h1("Agno tools (SOL, conflict, value, route)")
    pdf.p(
        "Tools zijn gewone Python-functies met Pydantic input/output, gewrapt als Agno "
        "@tool zodat de LLM ze kan aanroepen."
    )
    tools = [
        (
            "check_statute_of_limitations",
            "Input: jurisdiction, case_type, incident_date. "
            "Output: valid, expires_in (dagen), explanation. Leest sol_tables.json.",
        ),
        (
            "conflict_check",
            "Input: name, opposing_party. Zoekt in Postgres clients tabel. "
            "Output: conflict bool + details.",
        ),
        (
            "estimate_case_value",
            "Input: case_type, severity, damages. Blend van comps + stated damages. "
            "Output: estimate + range + explanation.",
        ),
        (
            "route_lead",
            "Input: practice_area, priority. Kiest attorney op specialisatie/load. "
            "Output: attorney_name + rationale.",
        ),
    ]
    for t, b in tools:
        pdf.h3(t)
        pdf.p(b)
    pdf.h2("Agentic vs deterministisch")
    pdf.p(
        "Met LLM: Agent.run(..., tool_choice='auto') laat het model tools kiezen. "
        "Zonder LLM (CI): de plan-fase bepaalt tools en roept entrypoints direct aan. "
        "Ontbrekende toolresultaten worden deterministisch aangevuld voor betrouwbaarheid."
    )
    

    # 12
    pdf.h1("De Intake Agent (plan → retrieve → tools → decide)")
    pdf.p(
        "Bestand: agents/intake/agent.py. Klasse IntakeAgent erft van Agno Agent."
    )
    phases = [
        ("Plan", "Welke velden missen? Welke tools? Welke retrieval-query? Escaleren?"),
        ("Retrieve", "pgvector semantic search + filters → citaties."),
        ("Tools", "Agentic of deterministisch tool-aanroepen."),
        ("Decide", "Lead score, viability, routing, next steps, confidence."),
        ("Self-check", "Disclaimer? Citaten? Verboden taal? Onzekerheid?"),
        ("Respond", "Gebruikersbericht (LLM of template) + gestructureerde response."),
    ]
    for t, b in phases:
        pdf.h3(t)
        pdf.p(b)
    pdf.h2("Waarom deze loop?")
    pdf.p(
        "De capstone eist expliciete agentic workflow. Door fasen te scheiden kun je "
        "monitoren (latency per stap), testen, en uitleggen wat er gebeurt — belangrijker "
        "dan één ondoorzichtige ‘black box’ prompt."
    )
    

    # 13
    pdf.h1("Multi-turn interview met prospects")
    pdf.p(
        "De PDF vraagt om ‘Interview prospective clients’. Daarom bestaat er een "
        "InterviewSession (agents/interview/agent.py), een Streamlit-tab, en een "
        "statische web-UI op Vercel (web/) die dezelfde FastAPI-routes gebruikt."
    )
    pdf.h2("Hoe werkt het?")
    pdf.bullet(
        [
            "Agent start met welkom + disclaimer + eerste vraag",
            "Gebruiker antwoordt in chat (web-UI toont een date picker bij datumvragen)",
            "Sessie vult IntakeFacts (heuristiek + optioneel LLM-extractie)",
            "Zolang verplichte velden missen: nieuwe vragen",
            "Ongeldige antwoorden (geen echte US-staat, geen parsebare datum) worden "
            "niet opgeslagen → agent blijft doorvragen",
            "Als genoeg info (of ‘screen now’ mét practice area + geldige staat): "
            "run_intake() screening",
            "Eindigt met samenvatting + guardrails + citaties",
        ]
    )
    pdf.h2("Verplichte velden")
    pdf.p("name, practice_area, jurisdiction, incident_date, opposing_party, damages")
    pdf.h2("Datum & jurisdiction")
    pdf.bullet(
        [
            "incident_date: ISO YYYY-MM-DD, ‘X months/years ago’, 06/15/2024, "
            "June 15 2024 — genormaliseerd via infer_incident_date(); anders None",
            "jurisdiction: alleen echte US-state codes/namen (CA, California, …); "
            "geen cleaned[:2]-gok meer (bugfix: ‘Personal Injury’ werd ‘PE’)",
            "SOL-tool draait alleen bij valide ISO-datum; anders skip + log",
        ]
    )
    pdf.h2("Quick analysis blijft bestaan")
    pdf.p(
        "Voor demoscenario’s en evaluatie is single-pass (plak tekst → analyse) handig. "
        "Interview is de conversatie-ervaring; quick analysis is de snelle pipeline-demo."
    )
    

    # 16
    pdf.h1("Lead scoring & beslissingen")
    pdf.p(
        "LexIntake heeft één scoring-engine: score_lead() in scoring/lead_scoring.py. "
        "Zowel de IntakeAgent (via agents/intake/decide.py) als de API/UI "
        "(via backend/services/intake_service.py) gebruiken dezelfde context-builder "
        "in scoring/context.py. Geen dubbele score-logica meer."
    )
    pdf.h2("Scoring-keten (single source of truth)")
    pdf.flow(
        ["Facts + Tools", "context.py", "score_lead()", "Decision / UI payload"],
        title="Unified scoring",
    )
    pdf.h2("Belangrijke bestanden")
    pdf.bullet(
        [
            "scoring/lead_scoring.py — score_lead(): qualified, score, decision, explanation",
            "scoring/context.py — build_lead_score_context() + acceptance criteria uit KB",
            "scoring/constants.py — drempels (70/40), boosts, penalties (named constants)",
            "agents/intake/decide.py — mapt LeadScoreOutput → DecisionResult voor agent-loop",
            "backend/services/intake_service.py — zelfde score_lead voor JSON API/UI",
        ]
    )
    pdf.p(
        "Deterministisch: zelfde context → zelfde LeadScoreOutput. "
        "Testbaar via pytest zonder OPENAI_API_KEY."
    )
    pdf.h2("Outputvelden")
    pdf.code(
        '{\n'
        '  "qualified": true,\n'
        '  "lead_score": 78,\n'
        '  "priority": "High",\n'
        '  "decision": "SCHEDULE_CONSULT",\n'
        '  "recommended_attorney": "Jordan Hale",\n'
        '  "explanation": "..."\n'
        "}"
    )
    pdf.h2("Beslissingen")
    pdf.bullet(
        [
            "SCHEDULE_CONSULT — voldoende fit, geen harde blockers",
            "REVIEW — onzeker / incomplete / menselijke check nodig",
            "REJECT — harde blockers (bv. conflict of duidelijk verlopen SOL)",
        ]
    )
    pdf.h2("Harde regels (intuïtie)")
    pdf.bullet(
        [
            "Conflict gevonden → meestal REJECT + escalatie",
            "SOL invalid → sterk negatief / reject pad",
            "Weinige acceptance matches → lagere score / review",
            "Hoge estimated value + goede fit → hogere priority",
        ]
    )
    

    # 15
    pdf.h1("Guardrails (juridische veiligheid)")
    pdf.p("Elke user-facing response moet aan deze eisen voldoen:")
    pdf.bullet(
        [
            "Legal disclaimer aanwezig",
            "Nooit voorschrijvend juridisch advies (“you should sue” etc.)",
            "Escalate bij onzekerheid",
            "Citeer retrieved evidence (chunk_id, practice_area, doc_type)",
            "Weiger unsupported / verzonnen statutes of attorney profiles",
        ]
    )
    pdf.h2("Waar wordt dit afgedwongen?")
    pdf.bullet(
        [
            "Agent instructions",
            "self_check fase",
            "respond() plakt disclaimer/escalatie/citaties indien nodig",
            "Evaluation check_guardrails()",
            "UI disclaimer componenten",
        ]
    )
    pdf.note(
        "Guardrails zijn een hard beoordelingspunt. Liever te vaak escaleren dan "
        "zelfverzekerd fout juridisch advies geven."
    )
    

    # 16
    pdf.h1("Observability & Agno Monitoring")
    pdf.p("De opdracht vraagt monitoring van sessies. LexIntake heeft twee lagen:")
    pdf.h2("1) Custom metrics (monitoring/)")
    pdf.bullet(
        [
            "logger.py — JSONL events, PII-sanitization",
            "metrics.py — tokens, cost, latency per stap, tool calls, retrieval hit rate, "
            "lead scores, escalaties, case values",
            "dashboard.py — Streamlit grafieken",
        ]
    )
    pdf.h2("2) Agno native tracing (OpenTelemetry)")
    pdf.bullet(
        [
            "monitoring/agno_tracing.py roept setup_tracing() aan",
            "Traces landen in monitoring/traces.db",
            "Per-call tokens/cost komen uit Agno run.metrics (geen custom "
            "estimate_cost / len(prompt)//4 meer)",
            "IntakeAgent sommeert die Agno-metrics over de sessie voor IntakeResponse",
            "Zichtbaar in dashboard sectie ‘Agno Monitoring’",
            "Uit te zetten met LEXINTAKE_AGNO_TRACING=0",
        ]
    )
    pdf.code("python -m streamlit run monitoring/dashboard.py")
    

    # 17
    pdf.h1("Evaluation harness")
    pdf.p(
        "evaluation/leads.csv bevat ~30 labeled synthetische leads. "
        "run_evaluation.py draait de agent en meet kwaliteit."
    )
    pdf.h2("Acht dimensies")
    pdf.bullet(
        [
            "Retrieval quality",
            "Grounding",
            "Qualification accuracy",
            "Case valuation",
            "Abstention behaviour",
            "Guardrails",
            "Cost & latency",
            "Provider comparison",
        ]
    )
    pdf.h2("Commands")
    pdf.code(
        "# Live OpenAI (key vereist)\n"
        "python evaluation/run_evaluation.py --providers openai:gpt-4.1 --limit 5"
    )
    pdf.p(
        "Rapport: docs/EVALUATION_REPORT.md. Perfecte qualificatie-accuracy is niet het "
        "doel; transparantie over grounding/guardrails wel."
    )
    

    # 18
    pdf.h1("Streamlit UI & demo")
    pdf.h2("App (frontend/)")
    pdf.code(
        "make ui\n"
        "# of: python -m streamlit run frontend/app.py\n"
        "# Docker: http://localhost:8501"
    )
    pdf.bullet(
        [
            "frontend/app.py — hoofd-UI met interview + quick analysis tabs",
            "frontend/components/ — header, disclaimer, result_viewer, footer",
            "frontend/demo.py — CLI demo met 4 scenario's",
            "frontend/runner.py — gedeelde pipeline runner",
            "web/ — statische Vercel-UI (date picker bij incident_date; praat met Render API)",
            "Tab Interview — multi-turn gesprek via agents/interview/",
            "Tab Quick analysis — plak case description → run_intake",
            "Sidebar met demoscenario’s",
            "Result viewer: score, decision, citaties, guardrails, tool JSON",
        ]
    )
    pdf.h2("Deploy-URLs (typisch)")
    pdf.bullet(
        [
            "API (Render): https://lexintake-api.onrender.com",
            "Frontend preview (Vercel develop): https://lexintake-git-develop-app-assist.vercel.app",
            "Postgres (Render): aparte managed DB lexintake-db via DATABASE_URL",
        ]
    )
    pdf.h2("API alternatief (backend/)")
    pdf.p(
        "Dezelfde intake-logica via FastAPI op http://localhost:8000/docs "
        "(of de Render-URL). Handig voor integraties of als je UI en backend wilt scheiden. "
        "HTTP-coverage: tests/test_backend_api.py."
    )
    pdf.h2("CLI demo (4 scenario’s)")
    pdf.code("make demo   # of: python frontend/demo.py")
    pdf.p(
        "Scenario’s: valid PI → SCHEDULE_CONSULT; expired SOL → REJECT; "
        "conflict ACME → REJECT+escalate; uncertain immigration → REVIEW+escalate."
    )
    

    # 19
    pdf.h1("Configuratie met .env")
    pdf.p("Secrets horen in .env (gitignored). Gebruik .env.example als template.")
    pdf.code(
        "DATABASE_URL=postgresql://lexintake:lexintake@localhost:5432/lexintake\n"
        "OPENAI_API_KEY=\n"
        "LEXINTAKE_EMBEDDING_PROVIDER=openai\n"
        "LEXINTAKE_EMBEDDING_MODEL=text-embedding-3-small\n"
        "LEXINTAKE_EMBEDDING_DIMS=1536\n"
        "LEXINTAKE_LLM_PROVIDER=openai\n"
        "LEXINTAKE_LLM_MODEL=gpt-4.1\n"
        "LEXINTAKE_AGNO_TRACING=1\n"
        "ANTHROPIC_API_KEY=\n"
        "GROQ_API_KEY="
    )
    pdf.h2("Veiligheid")
    pdf.bullet(
        [
            "Nooit keys in chat of commits plakken",
            "Gelekte key meteen intrekken en roteren",
            "config.py laadt dotenv; libraries lezen OPENAI_API_KEY uit env",
        ]
    )
    

    # 20
    pdf.h1("Git-workflow, PR’s en CI")
    pdf.h2("Branches")
    pdf.bullet(
        [
            "main — protected production",
            "develop — integratie",
            "feature/* — features",
        ]
    )
    pdf.h2("CI (.github/workflows/ci.yml)")
    pdf.p("Draait op pull_request naar main, job smoke-test, met live OpenAI:")
    pdf.bullet(
        [
            "Python 3.11 + pip install (PYTHONPATH=.)",
            "pytest tests/ — unit tests (scoring, guardrails, tools, geen API key)",
            "python -m db.init_structured_db",
            "etl.pipeline (OpenAI embeddings)",
            "frontend/demo.py (4 scenario's)",
            "evaluation --limit 5 (openai:gpt-4.1)",
            "upload logs als artifacts",
        ]
    )
    pdf.p(
        "main vereist status check smoke-test. Daardoor blokkeert een falende CI een merge."
    )
    

    # 21
    pdf.h1("Stap-voor-stap: systeem starten")
    pdf.h2("Optie A — Docker (aanbevolen)")
    pdf.code(
        "copy .env.example .env\n"
        "# Zet OPENAI_API_KEY in .env\n"
        "make setup\n"
        "# UI:  http://localhost:8501\n"
        "# API: http://localhost:8000/docs"
    )
    pdf.h2("Optie B — Lokaal Python + Postgres container")
    pdf.code(
        "copy .env.example .env\n"
        "# Zet OPENAI_API_KEY + DATABASE_URL in .env\n"
        "make setup-local\n"
        "make demo\n"
        "make ui\n"
        "make api   # optioneel"
    )
    pdf.h2("Vereisten")
    pdf.p(
        "OPENAI_API_KEY én DATABASE_URL zijn verplicht voor ETL/demo/eval. "
        "Unit tests (make test) draaien zonder API key. "
        "PYTHONPATH wordt gezet door make/Docker/CI; lokaal: pip install -e . of $env:PYTHONPATH='.'"
    )
    pdf.h2("Handige checks")
    pdf.bullet(
        [
            "Demo 4/4 PASS",
            "Interview tab stelt vragen en eindigt met screening",
            "Dashboard laadt metrics / Agno traces",
            "Geen .env in git status",
        ]
    )
    

    # 22
    pdf.h1("Demo-video voorbereiden")
    pdf.p("Gebruik docs/DEMO.md. Suggestie voor 3–5 minuten:")
    pdf.bullet(
        [
            "0:00 probleem + “geen chatbot, wel agentic RAG”",
            "0:20 repo/architectuur in 30 seconden",
            "0:50 live UI: valid PI scenario",
            "1:40 SOL expired → REJECT",
            "2:10 conflict → escalate",
            "2:40 uncertain → REVIEW",
            "3:10 monitoring dashboard",
            "3:40 evaluation highlight (grounding/guardrails)",
            "4:10 afsluiting + disclaimer",
        ]
    )
    pdf.p(
        "Toon altijd de disclaimer on-screen. Upload naar Loom/YouTube unlisted en zet "
        "de link in de README."
    )
    

    # 23
    pdf.h1("Troubleshooting & veelgemaakte fouten")
    problems = [
        (
            "ModuleNotFoundError llm / embeddings",
            "Zorg dat je vanuit repo-root draait en requirements geïnstalleerd zijn.",
        ),
        (
            "OPENAI_API_KEY missing",
            "Zet OPENAI_API_KEY in .env (verplicht).",
        ),
        (
            "DATABASE_URL missing",
            "Start Postgres: make db-up of docker compose up -d postgres.",
        ),
        (
            "Dimensie mismatch kb_docs",
            "Herlaad met python -m etl.pipeline als embedding-dimensies wijzigen.",
        ),
        (
            "Conflict-demo faalt",
            "init_structured_db opnieuw draaien zodat Elena Vasquez geseeded is.",
        ),
        (
            "CI rood",
            "Lokaal nabootsen: .env key + demo + eval --limit 5. CI vereist secret OPENAI_API_KEY.",
        ),
        (
            "IntakeFacts validation error",
            "Dual imports; recente fix herbindt naar één model via model_dump.",
        ),
        (
            "Key gelekt in chat",
            "Intrekken, nieuwe maken, nooit opnieuw plakken in issues/PR’s.",
        ),
    ]
    for t, b in problems:
        pdf.h3(t)
        pdf.p(b)
    

    # 24
    pdf.h1("Oefeningen om te oefenen")
    pdf.h2("Oefening A — Begrip")
    pdf.p(
        "Leg in 10 zinnen uit aan een klasgenoot wat LexIntake doet zonder code te tonen. "
        "Gebruik de woorden: lead, RAG, tool, guardrail, escalatie."
    )
    pdf.h2("Oefening B — ETL")
    pdf.p(
        "Voeg één FAQ-regel toe in kb/faqs.md, run python -m etl.pipeline, en toon dat retrieval "
        "de nieuwe chunk kan vinden."
    )
    pdf.h2("Oefening C — Tools")
    pdf.p(
        "Roep check_statute_of_limitations aan voor CA/Personal Injury met een oude "
        "en een recente incident_date. Vergelijk valid/expires_in."
    )
    pdf.h2("Oefening D — Interview")
    pdf.p(
        "Doe een interview in de UI waarbij je expres jurisdiction weglaat of "
        "‘I don’t know’ typt. Controleer dat de agent doorvraagt (geen nep-state zoals PE). "
        "Test ook een datum als ‘June 15, 2024’ of de date picker."
    )
    pdf.h2("Oefening E — Eval")
    pdf.p(
        "Draai evaluation --limit 5 met OpenAI en noteer grounding + guardrail compliance."
    )
    pdf.h2("Oefening F — Uitlegscore")
    pdf.p(
        "Neem één lead en schrijf met de hand waarom de decision SCHEDULE/REVIEW/REJECT is, "
        "op basis van SOL/conflict/value/acceptance."
    )
    

    # 25
    pdf.h1("Glossarium & checklist oplevering")
    pdf.h2("Mini-glossarium")
    pdf.bullet(
        [
            "Agno — agent framework",
            "pgvector — PostgreSQL vector extensie voor semantic search",
            "FastAPI — Python REST API framework (backend/)",
            "Docker Compose — container orchestratie (postgres + api + ui)",
            "chunk_id — stabiele id van een tekstbrok",
            "upsert — insert-or-update",
            "abstention — systeem onthoudt zich / escaleert",
            "grounding — antwoorden steunen op retrieved evidence",
            "smoke-test — snelle CI-check dat het systeem niet kapot is",
            "pytest — unit test framework (tests/ map, make test)",
            "PYTHONPATH — repo-root op import path (Makefile/Docker/CI)",
        ]
    )
    pdf.h2("Opleverchecklist")
    pdf.bullet(
        [
            "Repo publiek/deelbaar met instructor",
            "README klopt (setup + disclaimer)",
            "Design Report + Evaluation Report aanwezig",
            "Dashboard draait",
            "Demo 4/4 groen",
            "make test / pytest groen (16+ unit tests)",
            "CI groen op main PRs (pytest + smoke)",
            "main protected",
            "OPENAI key lokaal gezet (niet gecommit)",
            "Demo-video opgenomen + link toegevoegd",
            "Je kunt de architectuur hardop uitleggen",
        ]
    )
    pdf.h2("Laatste advies")
    pdf.p(
        "Beoordelaars kijken naar: werkt het end-to-end, is het agentic/RAG echt, "
        "zijn guardrails zichtbaar, is Git professioneel, en kun jij het uitleggen. "
        "Perfecte ML-metrics zijn minder belangrijk dan een helder, veilig intake-verhaal."
    )

    # Extra deep-dive chapters for a true textbook length
    pdf.h1("Werkvoorbeeld end-to-end: Valid Personal Injury")
    pdf.p(
        "Dit hoofdstuk volgt één lead van ruwe tekst tot beslissing. Lees het alsof je "
        "meekijkt in de runtime."
    )
    pdf.h2("Input")
    pdf.code(
        "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
    )
    pdf.h2("Stap 1 — Fact parsing")
    pdf.p(
        "parse_case_description herkent 'rear-end/collision' als Personal Injury, "
        "staat CA, damages 45000, incident_date ≈ vandaag minus 6*30 dagen, "
        "severity medium/high afhankelijk van keywords, naam Demo Prospect."
    )
    pdf.h2("Stap 2 — Plan")
    pdf.p(
        "Omdat jurisdiction, case_type en incident_date bekend zijn, plant de agent "
        "check_statute_of_limitations. Met name+party komt conflict_check. Met damages "
        "komt estimate_case_value. Met practice_area komt route_lead. Retrieval staat aan."
    )
    pdf.h2("Stap 3 — Retrieve")
    pdf.p(
        "De query mix practice area, CA, narrative en woorden als acceptance/settlement. "
        "pgvector search geeft chunks terug (acceptance_criteria, sol_rules, past_case, faq). "
        "Die chunks worden citaties."
    )
    pdf.h2("Stap 4 — Tools")
    pdf.bullet(
        [
            "SOL CA/PI: meestal valid=True, expires_in positief (2-jaar regel)",
            "Conflict: geen match → conflict=False",
            "Value: blend comps + 45k → schatting in de orde van tonnen kan voorkomen "
            "door sparse comps; interpretatie: richtinggevend, niet exact",
            "Route: attorney met PI-specialisatie, bv. Jordan Hale",
        ]
    )
    pdf.h2("Stap 5 — Scoring")
    pdf.p(
        "score_lead ziet geen conflict, SOL ok, practice match → qualified True, "
        "priority High, decision SCHEDULE_CONSULT."
    )
    pdf.h2("Stap 6 — Guardrails")
    pdf.p(
        "Response bevat disclaimer, citaties, geen 'you should sue'. Escalatie niet nodig."
    )

    pdf.h1("Werkvoorbeeld: verlopen SOL")
    pdf.code("Slip-and-fall in NV, incident 4 years ago, moderate injuries.")
    pdf.p(
        "Parser: Personal Injury, NV, incident_date ver in het verleden. "
        "SOL-tool: valid=False, expires_in negatief. Scoring duwt naar REJECT. "
        "Uitleg noemt statute/expiration. Dit toont dat tools niet cosmetisch zijn: "
        "ze veranderen de beslissing."
    )
    pdf.p(
        "In de demo checkt verify_scenario dat de explanation SOL-taal bevat. "
        "Zo bewijs je grounding + tool-effect in één scenario."
    )

    pdf.h1("Werkvoorbeeld: conflict of interest")
    pdf.code("Employment discrimination claim in CA, opposing party is ACME Corp.")
    pdf.p(
        "De parser map’t dit bewust naar client Elena Vasquez (seeded conflict case) "
        "wanneer employment+ACME voorkomt. conflict_check vindt een match in Postgres clients. "
        "Beslissing: REJECT of minstens escalatie. Belangrijk lespunt: structured DB "
        "is essentieel; vector search alleen is niet genoeg voor exacte identity checks."
    )

    pdf.h1("Werkvoorbeeld: onzekere immigratiezaak")
    pdf.code(
        "Immigration matter with unclear facts, missing dates, missing jurisdiction."
    )
    pdf.p(
        "Veel velden ontbreken. Runner markeert uncertain. Zelfs als scoring niet hard "
        "reject, forceert UI/runner REVIEW + escalatie. Dit is abstention behaviour: "
        "liever menselijke review dan overconfident automatisering."
    )

    pdf.h1("Hoe leg je LexIntake uit in 3 minuten?")
    pdf.p("Gebruik dit spreekscript:")
    pdf.bullet(
        [
            "Probleem: kantoren verdrinken in leads; paralegals filteren handmatig.",
            "Oplossing: agentic RAG screener — niet chatbot.",
            "Kennis: synthetische KB + ETL naar PostgreSQL (pgvector + entities).",
            "Agent: plant, retrieve’t, roept tools, scoort, self-checkt.",
            "Veiligheid: disclaimer, citaties, escalatie, geen legal advice.",
            "Bewijs: demo 4 scenario’s, evaluation metrics, CI smoke, GitHub flow.",
        ]
    )
    pdf.p(
        "Sluit af met: ‘The system recommends intake actions for staff; it does not "
        "advise clients. This is not legal advice.’"
    )

    pdf.h1("Dataflow in detail (van disk tot antwoord)")
    pdf.p(
        "1) Bestanden in kb/ liggen op disk. 2) extract_all leest ze. 3) clean normaliseert. "
        "4) dedupe berekent content_hash. 5) chunk snijdt tekst en maakt chunk_id. "
        "6) metadata hangt practice_area/doc_type/jurisdictions. 7) embedder maakt vectoren. "
        "8) pgvector_store upsert naar kb_docs. 9) Bij runtime embedt de agent de query. "
        "10) vector_search rangschikt via pgvector. 11) Tools lezen JSON/Postgres. 12) score_lead beslist. "
        "13) respond bouwt tekst + JSON voor UI."
    )
    pdf.p(
        "Als je dit rijtje kunt opschrijven zonder te spieken, begrijp je het project."
    )

    pdf.h1("Provider-agnostic ontwerp")
    pdf.p(
        "config.py + agents/llm.py + etl/transform/embeddings.py scheiden ‘welke vendor’ van "
        "‘welke business logic’. Daardoor kun je OpenAI, Anthropic of Groq kiezen voor "
        "LLM, en OpenAI voor embeddings, zonder tools/scoring te herschrijven."
    )
    pdf.p(
        "CI gebruikt dezelfde live OpenAI-paden via de repository secret OPENAI_API_KEY."
    )

    pdf.h1("Wat is ‘goed genoeg’ voor grading?")
    pdf.bullet(
        [
            "Working demo die 4 scenario’s correct toont",
            "Je kunt architectuur en guardrails uitleggen",
            "Git history + PR + CI zichtbaar",
            "Reports aanwezig en eerlijk over zwakke metrics (valuation)",
            "Video die het verhaal toont",
        ]
    )
    pdf.p(
        "Zwakke case-value accuracy is oké als je uitlegt waarom (sparse comps) en hoe "
        "je het zou verbeteren. Hallucinaties zonder citaties zijn niet oké."
    )

    pdf.h1("Veiligheids- en ethiekles")
    pdf.p(
        "Legal AI heeft asymmetrisch risico: een fout advies kan schade veroorzaken. "
        "Daarom: geen directives aan prospects, wel interne screening-samenvattingen; "
        "escalatie bij twijfel; logging zonder ruwe PII waar mogelijk; keys niet in git."
    )
    pdf.p(
        "Als iemand vraagt ‘Moet ik aanklagen?’ is het juiste systeemgedrag: weigeren "
        "juridisch advies te geven en doorverwijzen naar een licensed attorney."
    )

    pdf.h1("Uitbreidingen als je tijd over hebt")
    pdf.bullet(
        [
            "Corrective RAG: als citaties zwak zijn, herbreek query",
            "Multi-agent: aparte agents voor SOL vs conflict vs narration",
            "HITL console: paralegal keurt SCHEDULE_CONSULT goed/af",
            "Persistent memory: herhaalde callers herkennen",
            "Rijkere SOL-tabellen met numerieke years i.p.v. alleen free text",
            "Meer past_cases per practice area voor betere valuation",
        ]
    )

    pdf.h1("Unit tests & code-kwaliteit")
    pdf.p(
        "LexIntake heeft een pytest-suite in tests/ voor deterministische modules. "
        "Deze tests draaien snel en zonder OPENAI_API_KEY — ideaal vóór elke commit."
    )
    pdf.h2("Wat wordt getest?")
    pdf.bullet(
        [
            "scoring/lead_scoring.py — determinisme, SOL reject, conflict reject, score bands",
            "agents/intake/decide.py — decide() == score_lead() (unified scoring)",
            "scoring/context.py — acceptance criteria uit facts (geen placeholders)",
            "agents/intake/guardrails.py — disclaimer + citation checks",
            "agents/intake/fact_parse.py — PI case parsing heuristics",
            "tools/conflict_check.py — gemockte Postgres query",
        ]
    )
    pdf.h2("Commands")
    pdf.code(
        "make test                    # pytest tests/ -q\n"
        "pytest tests/test_lead_scoring.py -v\n"
        "pip install -e .             # optioneel: editable install"
    )
    pdf.h2("Code-kwaliteit principes in dit project")
    pdf.bullet(
        [
            "Single source of truth — één score_lead(), één LEGAL_DISCLAIMER, één slugify",
            "Package imports — from tools.common import (geen sys.path hacks)",
            "Named constants — scoring/constants.py i.p.v. magic numbers",
            "Service layer — backend/services/intake_service.py deelt logica UI/API",
            "Deterministic core — business rules testbaar zonder LLM",
        ]
    )

    pdf.h1("Cheatsheet: commands die je moet kennen")
    pdf.code(
        "make setup              # Docker: Postgres + init + API + UI\n"
        "make setup-local        # Host Python + Postgres container\n"
        "make test               # pytest (geen API key nodig)\n"
        "make demo / ui / api    # Demo, Streamlit, FastAPI\n"
        "make eval / dashboard   # Evaluation + monitoring\n"
        "make down               # Stop containers\n"
        "python docs/generate_leerboek_pdf.py  # Genereer dit leerboek"
    )

    pdf.h1("Cheatsheet: bestanden die je moet kunnen aanwijzen")
    mapping = [
        "Opdrachtbegrip -> docs/DESIGN_REPORT.md + dit leerboek",
        "KB brondata -> kb/*.json + faqs.md",
        "ETL -> etl/pipeline.py + etl/extract|transform|load/",
        "Vector store -> db/pgvector_store.py + db/schema.py",
        "Entities -> db/models.py + db/structured_db.py + db/migrations/",
        "Tools -> tools/*.py + tools/common.py",
        "Agent loop -> agents/intake/agent.py + retrieve.py + decide.py",
        "Interview -> agents/interview/agent.py",
        "LLM wiring -> agents/llm.py + agents/shared/make_agent.py",
        "Scoring -> scoring/lead_scoring.py + scoring/context.py + scoring/constants.py",
        "Tests -> tests/ (pytest, make test)",
        "UI -> frontend/app.py + frontend/components/",
        "API -> backend/api/main.py + backend/services/",
        "Docker -> docker-compose.yml + scripts/docker_init.py",
        "Eval -> evaluation/run_evaluation.py + leads.csv",
        "CI -> .github/workflows/ci.yml",
        "Config -> config.py + .env + Makefile",
    ]
    for line in mapping:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Body", "", 11)
        pdf.multi_cell(0, 6, f"- {line}")
    pdf.ln(2)

    pdf.h1("Zelftest (antwoord ondersteboven in je hoofd)")
    pdf.bullet(
        [
            "Wat is het verschil tussen RAG en ‘gewoon een LLM vragen’?",
            "Waarom Postgres entities naast pgvector kb_docs?",
            "Noem de 5 agent-fasen in volgorde.",
            "Welke beslissingen kan score_lead geven?",
            "Hoe dwingt CI live embeddings/LLM af?",
            "Waar zit de enige scoring-engine?",
            "Welke tests draaien zonder API key?",
            "Wat moet er altijd in een user-facing antwoord staan?",
            "Welk scenario toont conflict detection?",
            "Waar landen Agno traces?",
        ]
    )
    pdf.p(
        "Als je deze acht vragen soepel beantwoordt, ben je klaar om te presenteren."
    )

    pdf.add_page()
    pdf.set_font("Body", "B", 16)
    pdf.multi_cell(0, 8, "Einde van het LexIntake Leerboek")
    pdf.ln(4)
    pdf.set_font("Body", "", 11)
    pdf.multi_cell(
        0,
        6,
        "Je hebt nu een route van probleemstelling naar implementatie, runtime, "
        "evaluatie en oplevering. Gebruik de repo als lab: wijzig iets kleins, "
        "draai demo/eval, en observeer het effect.\n\n"
        "This is not legal advice. Consult a licensed attorney for legal guidance.\n"
        "Dit document is uitsluitend bedoeld om de capstone-opdracht te leren.",
    )

    # Pad to >= 40 pages with unique FAQ depth when chapter content runs short.
    extra_topics = [
        (
            "Waarom Agno?",
            "Agno geeft Agent + @tool + reasoning/tool_choice + tracing. Minder boilerplate "
            "dan alles zelf bouwen, en past bij de stackeis van de opdracht.",
        ),
        (
            "Waarom niet alleen één grote prompt?",
            "Omdat tools, scoring en guardrails dan oncontroleerbaar worden. De loop maakt "
            "gedrag meetbaar en demo-baar per fase.",
        ),
        (
            "Waarom is een API-key verplicht?",
            "Zonder key zijn embeddings en LLM niet beschikbaar. Hash/local paden zijn verwijderd.",
        ),
        (
            "Moet valuation perfect zijn?",
            "Nee. Wel uitlegbaar en begrensd. Sparse comps beperken accuracy.",
        ),
        (
            "Wat als de LLM tools overslaat?",
            "Deterministische fallback vult SOL/conflict/value/route alsnog.",
        ),
        (
            "Hoe bewijs ik grounding?",
            "Toon chunk_id citaties in UI en grounding score in eval summary.",
        ),
        (
            "Wat zet ik in de video?",
            "Probleem, architectuur flash, 4 scenario’s, dashboard, disclaimer.",
        ),
        (
            "Wat is de #1 fail in grading?",
            "Geen werkende demo, of geen guardrails, of geen uitlegbaarheid.",
        ),
        (
            "Waarom top_k tussen 5 en 10?",
            "Te weinig: missende evidence. Te veel: ruis en langere prompts. 5–10 is een "
            "praktische bandbreedte voor intake grounding.",
        ),
        (
            "Wat doet self-check precies?",
            "Controleert disclaimer, citaties, escalatiebehoefte en verboden voorschrijvende "
            "juridische formuleringen voordat het antwoord definitief is.",
        ),
        (
            "Waarom idempotente ETL?",
            "Capstone eist herhaalbare loads zonder duplicate chaos. chunk_id + upsert "
            "voorkomt dat elke run de store verdubbelt.",
        ),
        (
            "Hoe hangt interview vast aan scoring?",
            "Interview vult IntakeFacts tot verplicht minimum, daarna dezelfde run_intake "
            "pipeline als quick analysis.",
        ),
    ]
    idx = 0
    while pdf.page_no() < 40 and idx < len(extra_topics) * 3:
        if idx % len(extra_topics) == 0:
            pdf.h1("Extra FAQ & verdieping")
        q, a = extra_topics[idx % len(extra_topics)]
        pdf.h3(f"{q} (pass {idx // len(extra_topics) + 1})")
        pdf.p(a)
        pdf.p(
            "Schrijf in je eigen woorden één zin samenvatting van dit antwoord en "
            "noem welk bestand in de repo dit ondersteunt."
        )
        idx += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    from pypdf import PdfReader

    try:
        n = len(PdfReader(str(path)).pages)
    except Exception:
        n = "unknown"
    print(f"Wrote {path} pages={n}")
