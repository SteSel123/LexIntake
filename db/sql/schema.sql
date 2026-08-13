-- LexIntake structured entity schema (SQLite)
-- Complements LanceDB kb_docs (vectors) with relational entities.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    state TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attorneys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,
    experience_years INTEGER,
    jurisdictions TEXT, -- JSON array, e.g. ["CA","NV"]
    availability TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS past_cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    practice_area TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    facts TEXT NOT NULL,
    outcome TEXT,
    settlement_amount INTEGER,
    attorney_id TEXT,
    client_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (attorney_id) REFERENCES attorneys(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_clients_state ON clients(state);
CREATE INDEX IF NOT EXISTS idx_attorneys_availability ON attorneys(availability);
CREATE INDEX IF NOT EXISTS idx_past_cases_practice_area ON past_cases(practice_area);
CREATE INDEX IF NOT EXISTS idx_past_cases_jurisdiction ON past_cases(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_past_cases_attorney_id ON past_cases(attorney_id);
CREATE INDEX IF NOT EXISTS idx_past_cases_client_id ON past_cases(client_id);
