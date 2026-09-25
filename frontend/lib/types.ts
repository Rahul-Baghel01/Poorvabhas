export type SifSignal = "SIF_EVENT" | "SIF_POTENTIAL" | "NON_SIF" | "UNDETERMINED";
export type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type ReportStatus = "AI_ANALYZED" | "REVIEW_REQUIRED" | "HUMAN_CONFIRMED" | "HUMAN_REJECTED" | "PENDING";
export type GateAnswer = "YES" | "NO" | "INSUFFICIENT";

export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  role: "HSE_OFFICER" | "HSE_ADMIN";
  role_label: string;
  permissions: string[];
}

export interface ReportRow {
  id: number;
  report_id: string;
  report_type: string;
  date: string;
  site: string;
  site_code: string;
  location: string;
  activity: string;
  equipment: string | null;
  description: string;
  status: ReportStatus;
  scl_class: string | null;
  scl_label: string | null;
  sif_potential: boolean | null;
  sif_signal: SifSignal | null;
  primary_lsr: string | null;
  lsr_name: string | null;
  priority_score: number | null;
  priority_level: Priority | null;
  confidence: number | null;
  decision_source: "AI" | "HUMAN" | null;
  data_source: string;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size?: number;
  pages: number;
}

export interface Evidence {
  text: string;
  start: number | null;
  end: number | null;
  confidence: number;
  source: string;
}

export interface EntityOut {
  id?: number;
  entity_type: string;
  value: string;
  canonical: string | null;
  polarity: string | null;
  confidence: number;
  source: string;
  evidence: Evidence[];
}

export interface Gate {
  key: "high_energy" | "high_energy_event" | "direct_control" | "serious_injury";
  question: string;
  answer: GateAnswer;
  confidence: number;
  evidence: Evidence[];
  rationale: string;
  used_in_path: boolean;
}

export interface RuleCandidate {
  code: string;
  name: string;
  score: number;
  confidence: number;
  evidence: { kind: string; term: string; text: string; start: number | null; end: number | null }[];
}

export interface Mapping {
  primary: RuleCandidate;
  secondary: RuleCandidate[];
  candidates: RuleCandidate[];
  confidence: number;
  ambiguous: boolean;
  ambiguity_note: string | null;
  label: string;
  disclaimer: string;
}

export interface TraceStage {
  stage: string;
  label: string;
  status: string;
  detail: string;
  ms: number;
  data: Record<string, unknown>;
}

export interface PriorityPart {
  key: string;
  label: string;
  points: number;
  max: number;
  rationale: string;
}

export interface ConfidenceBreakdown {
  components: { key: string; label: string; value: number; weight: number; explanation: string }[];
  ml_agreement: number | null;
  penalty: number;
  penalty_reasons: string[];
}

export interface ReviewReason {
  code: string;
  detail: string;
  label?: string;
}

export interface AuditEntry {
  id: number;
  event_type: string;
  entity_type: string | null;
  entity_id: string | null;
  actor: string;
  summary: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Decision {
  id: number;
  action: string;
  original_prediction: Record<string, unknown>;
  decision: Record<string, unknown>;
  reviewer: string;
  reason: string | null;
  note: string | null;
  created_at: string;
}

export interface Analysis {
  id: number;
  model_version: string;
  created_at: string;
  entities: EntityOut[];
  not_stated: string[];
  features: { activity?: string; failed_barriers?: string[]; present_barriers?: string[]; energies?: string[]; hazards?: string[]; lsr?: string };
  scl: { gates: Gate[]; scl_class: string; scl_label: string; scl_description: string; candidates: string[]; decision_path: string[]; sif_potential: boolean | null; sif_signal: SifSignal; conflicts: string[] };
  sif_potential: boolean | null;
  sif_signal: SifSignal;
  mapping: Mapping;
  priority_score: number;
  priority_level: Priority;
  priority_breakdown: PriorityPart[];
  confidence: number;
  confidence_level: "HIGH" | "MEDIUM" | "LOW";
  confidence_breakdown: ConfidenceBreakdown;
  ml_probability: number | null;
  ml_model_version: string | null;
  ml_explanation: { term: string; weight: number }[];
  reasoning_summary: string;
  pipeline_trace: TraceStage[];
  review_reasons: ReviewReason[];
  context: { recurrence_count?: number; matching_patterns?: { pattern_id: number; code: string; name: string; occurrences: number }[] };
}

export interface ReviewItem {
  id: number;
  category: string;
  category_label: string;
  reasons: ReviewReason[];
  suggested_action: string;
  status: "OPEN" | "CLOSED";
  source: string;
  requested_by: string | null;
  priority_score: number;
  created_at: string;
  closed_at: string | null;
  report: ReportRow;
  analysis?: {
    confidence: number;
    confidence_level: string;
    ml_probability: number | null;
    scl_class: string;
    scl_candidates: string[];
    sif_signal: SifSignal;
    gates: Gate[];
    suggested_lsr: RuleCandidate | null;
    secondary_lsr: RuleCandidate[];
    reasoning_summary: string;
  };
}

export interface ReportDetail {
  report: ReportRow & {
    worker_role: string | null;
    contractor: string | null;
    injury_severity: string | null;
    shift: string | null;
    weather: string | null;
    created_at: string;
    updated_at: string;
    is_synthetic: boolean;
  };
  analysis: Analysis | null;
  review: ReviewItem | null;
  decisions: Decision[];
  audit: AuditEntry[];
  patterns: { id: number; code: string; name: string; occurrences: number; trend: string }[];
  analysis_count: number;
}

export interface Dist {
  name: string;
  count: number;
}

export interface TrendDetail {
  trend: string;
  bucket: string;
  labels: string[];
  counts: number[];
  n_events: number;
  reason?: string;
  ewma?: number[];
  ewma_ucl?: number;
  ewma_lcl?: number;
  cusum_pos?: number[];
  cusum_h?: number;
  baseline_mean?: number;
  recent_mean?: number;
  method?: string;
}

export interface PatternOut {
  id: number;
  code: string;
  name: string;
  method: string;
  signature: { activity?: string | null; barrier?: string | null; energy?: string | null; lsr?: string | null };
  occurrences: number;
  sif_occurrences: number;
  sites: Dist[];
  locations: Dist[];
  activities: Dist[];
  barriers: Dist[];
  energy_sources: Dist[];
  associated_lsr: { code: string; name: string; count: number }[];
  primary_lsr: string | null;
  lsr_name: string | null;
  trend: string;
  trend_detail: TrendDetail;
  cohesion: number;
  confidence: number;
  first_seen: string | null;
  last_seen: string | null;
  run_id: string;
  created_at: string;
  reports?: (ReportRow & { membership: number })[];
}

export interface RankItem {
  key: string;
  label: string;
  rank: number;
  raw_rank: number;
  total_reports: number;
  sif_potential_reports: number;
  sif_events: number;
  high_priority: number;
  mean_priority: number;
  raw_rate: number | null;
  eb_rate: number;
  eb_rate_ci90: [number, number];
  raw_precursor_count: number;
  exposure_hours?: number;
  raw_density: number | null;
  eb_density: number | null;
  eb_density_ci90?: [number, number];
  adjusted_score: number;
  notes: string[];
  site?: string;
}

export interface Ranking {
  dimension: string;
  days: number | null;
  items: RankItem[];
  method: { score?: string; exposure_note?: string; definition?: string; rate_prior?: { dataset_rate: number | null } };
  note?: string;
}

export interface Kpi {
  value: number | null;
  previous?: number;
  change_pct?: number | null;
}

export interface Dashboard {
  window: { days: number; start: string; end: string };
  kpis: {
    total_reports: Kpi;
    sif_potential_reports: Kpi & { sif_events: number; share: number | null };
    recurring_patterns: Kpi & { increasing: number };
    review_queue: Kpi;
    high_priority_signals: Kpi;
    lsr_coverage: Kpi & { mapped: number; sif_signals: number; rules_observed: number; rules_total: number };
  };
  priority_banner: { awaiting_human_validation: number; text: string | null };
  sif_distribution: { signal: string; count: number }[];
  scl_distribution: { scl_class: string; count: number }[];
  reports_over_time: { week_start: string; total: number; sif: number }[];
  top_lsr: { code: string; name: string; count: number }[];
  top_activities: { activity: string; total: number; sif: number }[];
  top_sites: { site: string; total: number; sif: number }[];
  patterns: { id: number; code: string; name: string; occurrences: number; trend: string; primary_lsr: string; lsr_name: string; sites: string[]; counts: number[] }[];
  review_queue: { review_id: number; report_id: string; category: string; priority_score: number; activity: string; site: string; scl_class: string; sif_signal: SifSignal }[];
  site_ranking: Ranking;
}
