# Data model

PostgreSQL 16 with the `vector` extension (pgvector). The same SQLAlchemy models run on SQLite in unit tests (the embedding column falls back to a JSON array). Local startup initializes tables with `db.init_db`; Vercel requires the explicit initializer in [vercel-deployment.md](vercel-deployment.md). Source: `backend/app/models.py`.

## Entity overview

```
roles ─< users
sites ─< reports ─< report_analysis ─< entities ─< evidence_spans
                 │                  ├─ scl_classifications (1:1)
                 │                  └─< rule_mappings
                 ├─< review_queue ─< review_decisions ─< feedback_examples
                 ├─< pattern_reports >─ patterns
                 └── embeddings (1:1, vector(64))
taxonomy_rules · model_versions · audit_logs · dashboard_snapshots · system_settings
```

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `roles` | HSE_OFFICER, HSE_ADMIN | `name`, `label`, `permissions` (JSON) |
| `users` | accounts | `username`, `full_name`, `password_hash` (bcrypt), `role_id`, `is_active` |
| `sites` | sites | `code`, `name`, `region`, `site_type`, `exposure_hours` (synthetic), `is_synthetic` |
| `reports` | the report as entered | `report_id`, `report_type`, `date`, `site_id`, `location`, `activity`, `equipment`, `description`, `worker_role`, `contractor`, `injury_severity`, `shift`, `weather`, `data_source`, timestamps. **Current decision (denormalised for filtering):** `status`, `scl_class`, `sif_potential`, `sif_signal`, `primary_lsr`, `priority_score`, `priority_level`, `confidence`, `decision_source` (AI/HUMAN), `current_analysis_id`. **Synthetic only:** `reference_scl_class`, `reference_sif_potential`, `reference_lsr` |
| `report_analysis` | one row per engine run (history kept, `is_current`) | `model_version`, `energy_present`/`energy_confidence`, `control_present`/`control_confidence`, `high_energy_event`, `serious_injury`, `scl_class`, `scl_candidates`, `sif_potential`, `sif_signal`, `confidence`, `confidence_level`, `confidence_breakdown`, `priority_score`, `priority_level`, `priority_breakdown`, `ml_probability`, `ml_model_version`, `ml_explanation`, `primary_lsr`, `mapping_confidence`, `extraction` (features, SCL + mapping snapshot), `reasoning_summary`, `pipeline_trace`, `review_reasons`, `created_at` |
| `entities` | extracted entities | `entity_type`, `value`, `canonical`, `polarity`, `confidence`, `source` |
| `evidence_spans` | exact source text | `field` (entity type or `gate.<key>`), `text`, `start_offset`, `end_offset`, `confidence`, `source` (description / structured_field / rule) |
| `scl_classifications` | gate answers | `q_high_energy`, `q_high_energy_event`, `q_direct_control`, `q_serious_injury`, `decision_path`, `gate_details`, `candidate_classes`, `scl_class`, `sif_potential`, `conflicts` |
| `taxonomy_rules` | IOGP rules | `code`, `rule_number`, `name`, `description`, `keywords`, `phrases`, `weight`, `is_active`, `is_fallback`, `updated_by` |
| `rule_mappings` | ranked rules per analysis | `rule_code`, `rank`, `is_primary`, `score`, `confidence`, `evidence` |
| `patterns` | mined patterns (per run, `is_current`) | `pattern_code`, `name`, `method`, `signature`, `occurrences`, `sif_occurrences`, `sites`, `locations`, `activities`, `barriers`, `energy_sources`, `associated_lsr`, `trend`, `trend_detail`, `cohesion`, `confidence`, `first_seen`, `last_seen` |
| `pattern_reports` | membership | `pattern_id`, `report_id`, `membership` |
| `review_queue` | review items | `category`, `reasons`, `suggested_action`, `status`, `source` (AUTO/MANUAL), `requested_by`, `priority_score`, `closed_at` |
| `review_decisions` | every decision | `action`, `original_prediction`, `decision`, `reviewer_id`, `reviewer_name`, `reason`, `note`, `created_at` |
| `feedback_examples` | training signal | `text`, `label_*`, `predicted_*`, `is_correction`, `used_in_model_version` |
| `model_versions` | engine / classifier / embedder versions | `version`, `component`, `algorithm`, `params`, `metrics` (null until computed), `evaluation_basis`, `n_train`, `n_test`, `artifact_path`, `is_active` |
| `model_artifacts` | durable classifier and embedder joblib bytes across backend instances | `version`, `payload` |
| `pending_imports` | validated CSV rows and one-use tokens, tied to a user | `token`, `user_id`, `created_at_epoch`, `rows` |
| `embeddings` | similarity vectors | `report_id`, `model`, `vector` (pgvector `vector(64)`) |
| `audit_logs` | traceability | `event_type`, `entity_type`, `entity_id`, `actor_name`, `summary`, `details`, `created_at` |
| `dashboard_snapshots` | KPI snapshots at key events | `trigger`, `payload` |
| `system_settings` | configurable engine settings | `key`, `value`, `updated_by` |

## Report status lifecycle

```
PENDING → AI_ANALYZED ("Engine analyzed") ──(manual request)──▶ REVIEW_REQUIRED ("Review required")
        └→ REVIEW_REQUIRED ──decision leaves the engine result unchanged──▶ HUMAN_CONFIRMED ("Expert confirmed")
                          └──decision changes SCL class / SIF-potential / LSR──▶ HUMAN_REJECTED ("Expert corrected")
```

Stored status values are unchanged for compatibility with existing data; the UI labels are shown in quotes. Every decision except `NOTE` stores a labelled `feedback_examples` row (`is_correction` when the result changed). Retraining is an explicit admin action.

Once `decision_source = HUMAN`, re-analysis updates the stored analysis (for traceability) but never overwrites the reviewer's SCL class, SIF potential or rule.

## Audit event types

`REPORT_CREATED`, `REPORT_ANALYZED`, `SIF_CLASSIFIED`, `RULE_MAPPED`, `REVIEW_STARTED`, `REVIEW_COMPLETED`, `TAXONOMY_CHANGED`, `MODEL_CHANGED`, `IMPORT_COMPLETED`, `SETTINGS_CHANGED`, `PATTERNS_MINED`, `USER_LOGIN`, `DATASET_SEEDED`.
