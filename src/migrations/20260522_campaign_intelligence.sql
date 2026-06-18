-- Campaign Intelligence Engine migration
-- Links internal campaign records to Meta campaign IDs and stores performance metrics.

CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY,
  internal_campaign_id VARCHAR(160) UNIQUE NOT NULL,
  meta_campaign_id VARCHAR(160) UNIQUE DEFAULT '',
  product_id VARCHAR(160) DEFAULT '',
  product_name VARCHAR(180) DEFAULT '',
  strategy_version VARCHAR(20) DEFAULT 'V1',
  status VARCHAR(40) DEFAULT 'ACTIVE',
  daily_budget FLOAT DEFAULT 0,
  spend_today FLOAT DEFAULT 0,
  target_cpa FLOAT DEFAULT 0,
  target_roas FLOAT DEFAULT 1,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS campaign_metrics (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
  date DATETIME,
  ctr FLOAT DEFAULT 0,
  cpc FLOAT DEFAULT 0,
  cpm FLOAT DEFAULT 0,
  spend FLOAT DEFAULT 0,
  purchases INTEGER DEFAULT 0,
  cost_per_purchase FLOAT DEFAULT 0,
  roas FLOAT DEFAULT 0,
  connect_rate FLOAT DEFAULT 0,
  checkout_rate FLOAT DEFAULT 0,
  capi_status VARCHAR(40) DEFAULT 'ok',
  source VARCHAR(40) DEFAULT 'manual',
  created_at DATETIME
);

CREATE TABLE IF NOT EXISTS ad_library_benchmarks (
  id INTEGER PRIMARY KEY,
  niche VARCHAR(120) NOT NULL,
  geo VARCHAR(80) DEFAULT '',
  language VARCHAR(80) DEFAULT '',
  creative_pattern VARCHAR(180) DEFAULT '',
  hook_pattern VARCHAR(180) DEFAULT '',
  days_active INTEGER DEFAULT 0,
  estimated_strength_score FLOAT DEFAULT 0,
  benchmark_ctr FLOAT DEFAULT 1.0,
  source_ad_id VARCHAR(160) DEFAULT '',
  captured_at DATETIME
);

CREATE TABLE IF NOT EXISTS performance_tickets (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
  severity VARCHAR(20) DEFAULT 'yellow',
  reason_code VARCHAR(100),
  action_recommended VARCHAR(180) DEFAULT 'monitor',
  reasoning TEXT DEFAULT '',
  status VARCHAR(40) DEFAULT 'open',
  created_at DATETIME
);

-- Safe local migration for existing SQLite databases
ALTER TABLE campaigns ADD COLUMN meta_adset_id TEXT DEFAULT '';
