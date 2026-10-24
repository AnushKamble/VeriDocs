export type AnswerStatus = 
  | 'answered' 
  | 'partially_supported' 
  | 'abstained' 
  | 'conflicting_evidence' 
  | 'generation_error' 
  | 'auditor_unavailable';

export type AuditStatus = 
  | 'SUPPORTED' 
  | 'CONTRADICTED' 
  | 'NUMERIC_MISMATCH' 
  | 'INVALID_CITATION' 
  | 'INSUFFICIENT_EVIDENCE' 
  | 'CONFLICTING_EVIDENCE' 
  | 'AUDITOR_UNAVAILABLE' 
  | 'NEEDS_REVIEW';

export interface NumericFact {
  metric: string;
  raw_value: string;
  numeric_value?: number | null;
  unit?: string | null;
  period?: string | null;
}

export interface AtomicClaim {
  claim_id: string;
  text: string;
  claim_kind: 'numeric' | 'narrative' | 'comparison';
  source_chunk_ids: string[];
  numeric_facts: NumericFact[];
  audit_status: AuditStatus;
  audit_reason: string;
  nli_entailment_score?: number | null;
  nli_contradiction_score?: number | null;
}

export interface ChunkRecord {
  chunk_id: string;
  document_id: string;
  chunk_kind: 'narrative' | 'table_group' | 'table_row' | 'footnote';
  ordinal: number;
  section_id: string;
  section_title: string;
  text: string;
  raw_text: string;
  token_count: number;
  table_id?: string | null;
  row_labels: string[];
  column_labels: string[];
  units?: string | null;
  source_url: string;
  source_locator: string;
  content_hash: string;
}

export interface RetrievalCandidate {
  chunk_id: string;
  document_id: string;
  retriever: string;
  rank: number;
  raw_score: number;
  rrf_score?: number | null;
  text_preview: string;
}


export interface RetrievalTrace {
  query_id: string;
  query_text: string;
  applied_filters: Record<string, any>;
  bm25_candidates: RetrievalCandidate[];
  dense_candidates: RetrievalCandidate[];
  fused_candidates: RetrievalCandidate[];
  reranked_candidates: RetrievalCandidate[];
  final_evidence_chunk_ids: string[];
  timings_ms: Record<string, number>;
}

export interface QueryResponse {
  query_id: string;
  answer_status: AnswerStatus;
  summary: string;
  claims: AtomicClaim[];
  retrieved_evidence: ChunkRecord[];
  retrieval_trace: RetrievalTrace;
  model_version: string;
  prompt_version: string;
  limitations: string[];
}

export interface FilingDocument {
  document_id: string;
  cik: string;
  ticker?: string | null;
  company_name: string;
  form_type: string;
  accession_number: string;
  filing_date: string;
  report_period: string;
  fiscal_year?: number | null;
  fiscal_quarter?: number | null;
  primary_document_name: string;
  source_url: string;
  byte_size: number;
  status: string;
}
