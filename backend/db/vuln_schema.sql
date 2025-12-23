-- Vulnerability Database Schema
-- Optimized for fast scanning of bugs/PSIRTs against device versions and labels

-- Main vulnerabilities table: One row per bug/PSIRT
CREATE TABLE IF NOT EXISTS vulnerabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    bug_id TEXT NOT NULL UNIQUE,
    advisory_id TEXT,  -- For PSIRTs (e.g., cisco-sa-xxx)
    vuln_type TEXT NOT NULL,  -- 'bug' or 'psirt'

    -- Metadata
    severity INTEGER,  -- 1-6 for bugs, CVSS for PSIRTs
    headline TEXT,
    summary TEXT,
    url TEXT,
    status TEXT,  -- Open, Fixed, etc.

    -- Platform
    platform TEXT NOT NULL,  -- IOS-XE, IOS-XR, ASA, FTD, NX-OS
    product_series TEXT,  -- Catalyst 9300, etc.

    -- Version information (normalized)
    -- These columns support fast scanning without parsing version_pattern on every query
    affected_versions_raw TEXT NOT NULL,  -- Original text: "17.10.1 17.12.4 17.13.1"
    version_pattern TEXT NOT NULL,  -- EXPLICIT, WILDCARD, OPEN_LATER, OPEN_EARLIER, MAJOR_WILDCARD
    version_min TEXT,  -- Minimum affected version (normalized: 17.10.1 → 17.10.1)
    version_max TEXT,  -- Maximum affected version (for EXPLICIT/OPEN_EARLIER)
    fixed_version TEXT,  -- First fixed release (for "and later" checking)

    -- Labels (JSON array)
    labels TEXT,  -- JSON: ["MGMT_SSH_HTTP", "SEC_CoPP"]
    labels_source TEXT,  -- 'gpt4o_high_confidence', 'unlabeled', etc.

    -- Metadata
    last_modified TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for fast queries
    CONSTRAINT chk_vuln_type CHECK (vuln_type IN ('bug', 'psirt')),
    CONSTRAINT chk_version_pattern CHECK (version_pattern IN ('EXPLICIT', 'WILDCARD', 'OPEN_LATER', 'OPEN_EARLIER', 'MAJOR_WILDCARD', 'UNKNOWN'))
);

-- Version index: Fast lookups for version scanning
-- One row per distinct version mentioned in affected_versions_raw
CREATE TABLE IF NOT EXISTS version_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vulnerability_id INTEGER NOT NULL,
    version_normalized TEXT NOT NULL,  -- 17.10.1 → 17.10.1 (strip leading zeros, pad)
    version_major INTEGER NOT NULL,  -- 17
    version_minor INTEGER,  -- 10
    version_patch INTEGER,  -- 1

    FOREIGN KEY (vulnerability_id) REFERENCES vulnerabilities(id) ON DELETE CASCADE
);

-- Label index: Fast lookups for label-based queries
-- One row per label per vulnerability
CREATE TABLE IF NOT EXISTS label_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vulnerability_id INTEGER NOT NULL,
    label TEXT NOT NULL,  -- MGMT_SSH_HTTP

    FOREIGN KEY (vulnerability_id) REFERENCES vulnerabilities(id) ON DELETE CASCADE
);

-- Database metadata: Track incremental updates
CREATE TABLE IF NOT EXISTS db_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance (<100ms for 2,819 bugs)
CREATE INDEX IF NOT EXISTS idx_vuln_platform ON vulnerabilities(platform);
CREATE INDEX IF NOT EXISTS idx_vuln_type ON vulnerabilities(vuln_type);
CREATE INDEX IF NOT EXISTS idx_vuln_bug_id ON vulnerabilities(bug_id);
CREATE INDEX IF NOT EXISTS idx_vuln_pattern ON vulnerabilities(version_pattern);

CREATE INDEX IF NOT EXISTS idx_version_vuln_id ON version_index(vulnerability_id);
CREATE INDEX IF NOT EXISTS idx_version_normalized ON version_index(version_normalized);
CREATE INDEX IF NOT EXISTS idx_version_major_minor ON version_index(version_major, version_minor);

CREATE INDEX IF NOT EXISTS idx_label_vuln_id ON label_index(vulnerability_id);
CREATE INDEX IF NOT EXISTS idx_label_name ON label_index(label);

-- Initial metadata entries
INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('schema_version', '1.0');
INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('last_update', '');
INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('total_vulnerabilities', '0');
