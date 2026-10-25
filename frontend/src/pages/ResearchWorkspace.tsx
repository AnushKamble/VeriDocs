import React, { useState } from 'react';
import { AtomicClaim, ChunkRecord, QueryResponse } from '../types';
import { Search, SlidersHorizontal, CheckCircle2, AlertTriangle, XCircle, HelpCircle, ShieldAlert } from 'lucide-react';

interface ResearchWorkspaceProps {
  onSelectEvidence: (chunk: ChunkRecord, trace: any) => void;
}

const SAMPLE_PROMPTS = [
  "What were Apple's total net sales in fiscal 2023?",
  "Compare Microsoft Azure revenue growth with Server products",
  "What was NVIDIA Compute revenue and gross margin in fiscal 2024?",
  "What were Alphabet's capital expenditures in 2023?",
];

export const ResearchWorkspace: React.FC<ResearchWorkspaceProps> = ({ onSelectEvidence }) => {
  const [query, setQuery] = useState('');
  const [ticker, setTicker] = useState('AAPL');
  const [formType, setFormType] = useState('10-K');
  const [retrieverMode, setRetrieverMode] = useState('hybrid_rrf');
  const [topK, setTopK] = useState(5);
  const [enableNli, setEnableNli] = useState(true);
  const [showFilters, setShowFilters] = useState(false);

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (queryText?: string) => {
    const q = (queryText || query).trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          filters: ticker ? { ticker } : undefined,
          retriever_mode: retrieverMode,
          top_k: topK,
          enable_nli: enableNli,
        }),
      });

      if (!res.ok) {
        throw new Error(`Query failed with status ${res.status}`);
      }
      const data: QueryResponse = await res.json();
      setResponse(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred while executing the query.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'answered': return { bg: '#ecfdf5', border: '#a7f3d0', text: '#065f46', badge: '#10b981' };
      case 'partially_supported': return { bg: '#fffbeb', border: '#fde68a', text: '#92400e', badge: '#f59e0b' };
      case 'abstained': return { bg: '#f1f5f9', border: '#cbd5e1', text: '#334155', badge: '#64748b' };
      case 'conflicting_evidence': return { bg: '#fef2f2', border: '#fecaca', text: '#991b1b', badge: '#ef4444' };
      case 'generation_error': return { bg: '#fef2f2', border: '#fecaca', text: '#991b1b', badge: '#dc2626' };
      case 'auditor_unavailable': return { bg: '#fffbeb', border: '#fde68a', text: '#92400e', badge: '#d97706' };
      default: return { bg: '#f8fafc', border: '#e2e8f0', text: '#475569', badge: '#94a3b8' };
    }
  };

  const getClaimStatusBadge = (status: string) => {
    switch (status) {
      case 'SUPPORTED':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#dcfce7', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><CheckCircle2 size={12} /> SUPPORTED</span>;
      case 'NUMERIC_MISMATCH':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#fee2e2', color: '#991b1b', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><ShieldAlert size={12} /> NUMERIC MISMATCH</span>;
      case 'CONTRADICTED':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#fee2e2', color: '#991b1b', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><XCircle size={12} /> CONTRADICTED</span>;
      case 'INVALID_CITATION':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#fef3c7', color: '#92400e', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><AlertTriangle size={12} /> INVALID CITATION</span>;
      case 'AUDITOR_UNAVAILABLE':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#fff7ed', color: '#c2410c', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><HelpCircle size={12} /> AUDITOR UNAVAILABLE</span>;
      case 'NEEDS_REVIEW':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#fef3c7', color: '#92400e', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><AlertTriangle size={12} /> NEEDS REVIEW</span>;
      case 'INSUFFICIENT_EVIDENCE':
        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#f1f5f9', color: '#475569', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}><HelpCircle size={12} /> INSUFFICIENT</span>;
      default:
        return <span style={{ backgroundColor: '#f1f5f9', color: '#475569', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}>{status}</span>;
    }
  };

  const handleCitationClick = (chunkId: string) => {
    if (!response) return;
    const chunk = response.retrieved_evidence.find(c => c.chunk_id === chunkId);
    if (chunk) {
      onSelectEvidence(chunk, response.retrieval_trace);
    }
  };

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '20px 0' }}>
      {/* Search Input Section */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <input
              type="text"
              placeholder="Ask a grounded financial question (e.g. What were Apple's net sales in 2023?)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '15px',
                outline: 'none',
              }}
            />
          </div>
          <button
            onClick={() => handleSearch()}
            disabled={loading}
            style={{
              padding: '12px 24px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Search size={18} />
            {loading ? 'Auditing...' : 'Analyze'}
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            style={{
              padding: '12px 16px',
              backgroundColor: showFilters ? '#eff6ff' : '#f8fafc',
              border: '1px solid #cbd5e1',
              borderRadius: '8px',
              cursor: 'pointer',
              color: '#334155',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <SlidersHorizontal size={16} /> Filters
          </button>
        </div>

        {/* Filter Controls */}
        {showFilters && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', marginTop: '12px', border: '1px solid #e2e8f0' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>TICKER</label>
              <select
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', marginTop: '4px' }}
              >
                <option value="AAPL">AAPL (Apple)</option>
                <option value="MSFT">MSFT (Microsoft)</option>
                <option value="GOOGL">GOOGL (Alphabet)</option>
                <option value="NVDA">NVDA (NVIDIA)</option>
                <option value="">All Companies</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>FORM TYPE</label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', marginTop: '4px' }}
              >
                <option value="10-K">Form 10-K (Annual)</option>
                <option value="10-Q">Form 10-Q (Quarterly)</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>RETRIEVER</label>
              <select
                value={retrieverMode}
                onChange={(e) => setRetrieverMode(e.target.value)}
                style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', marginTop: '4px' }}
              >
                <option value="hybrid_rrf">Hybrid RRF</option>
                <option value="bm25">BM25 Only</option>
                <option value="dense">Dense FAISS</option>
                <option value="reranked">Reranked</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>TOP K: {topK}</label>
              <input
                type="range"
                min="1"
                max="15"
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value))}
                style={{ width: '100%', marginTop: '8px' }}
              />
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input
                  type="checkbox"
                  id="enableNliCheck"
                  checked={enableNli}
                  onChange={(e) => setEnableNli(e.target.checked)}
                />
                <label htmlFor="enableNliCheck" style={{ fontSize: '11px', color: '#334155', cursor: 'pointer' }}>
                  Enable NLI Audit
                </label>
              </div>
            </div>

          </div>
        )}

        {/* Prompt Suggestions */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
          <span style={{ fontSize: '12px', color: '#64748b', alignSelf: 'center' }}>Examples:</span>
          {SAMPLE_PROMPTS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => { setQuery(p); handleSearch(p); }}
              style={{
                backgroundColor: '#f1f5f9',
                border: 'none',
                padding: '4px 10px',
                borderRadius: '16px',
                fontSize: '12px',
                color: '#334155',
                cursor: 'pointer',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{ padding: '12px 16px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#991b1b', marginBottom: '20px', fontSize: '14px' }}>
          {error}
        </div>
      )}

      {/* Grounded Response View */}
      {response && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Main Answer Header Card */}
          {(() => {
            const colors = getStatusColor(response.answer_status);
            return (
              <div style={{ backgroundColor: colors.bg, border: `1px solid ${colors.border}`, borderRadius: '12px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span style={{
                    backgroundColor: colors.badge,
                    color: '#ffffff',
                    padding: '4px 12px',
                    borderRadius: '16px',
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}>
                    {response.answer_status.replace('_', ' ')}
                  </span>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>
                    Model: {response.model_version} | Latency: {response.retrieval_trace?.timings_ms?.total_query_execution_ms || 0}ms
                  </span>
                </div>
                <div style={{ fontSize: '16px', lineHeight: 1.6, color: colors.text, fontWeight: 500 }}>
                  {response.summary}
                </div>
              </div>
            );
          })()}

          {/* Claims List with Citations and Numeric Audit */}
          {response.claims && response.claims.length > 0 && (
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#0f172a', marginBottom: '12px' }}>
                Atomic Grounded Claims ({response.claims.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {response.claims.map((claim: AtomicClaim, idx: number) => (
                  <div key={claim.claim_id || idx} style={{
                    backgroundColor: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '16px',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b' }}>
                        CLAIM #{idx + 1} ({claim.claim_kind.toUpperCase()})
                      </span>
                      {getClaimStatusBadge(claim.audit_status)}
                    </div>

                    <div style={{ fontSize: '14px', color: '#1e293b', lineHeight: 1.5, marginBottom: '12px' }}>
                      {claim.text}
                    </div>

                    {/* Numeric Facts if any */}
                    {claim.numeric_facts && claim.numeric_facts.length > 0 && (
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
                        {claim.numeric_facts.map((nf, nIdx) => (
                          <span key={nIdx} style={{
                            backgroundColor: '#f8fafc',
                            border: '1px solid #cbd5e1',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            fontSize: '11px',
                            color: '#334155',
                          }}>
                            {nf.metric}: <strong>{nf.raw_value}</strong> {nf.unit && `(${nf.unit})`} {nf.period && `[${nf.period}]`}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Citations and NLI Probabilities Footer */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #f1f5f9', paddingTop: '10px' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', color: '#64748b' }}>Sources:</span>
                        {claim.source_chunk_ids.map((cid) => (
                          <button
                            key={cid}
                            onClick={() => handleCitationClick(cid)}
                            style={{
                              backgroundColor: '#eff6ff',
                              color: '#2563eb',
                              border: '1px solid #bfdbfe',
                              borderRadius: '4px',
                              padding: '2px 8px',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            [{cid.slice(0, 18)}...]
                          </button>
                        ))}
                      </div>

                      {claim.nli_entailment_score !== null && claim.nli_entailment_score !== undefined && (
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                          NLI Entailment: <strong>{(claim.nli_entailment_score * 100).toFixed(1)}%</strong> | Contra: <strong>{((claim.nli_contradiction_score || 0) * 100).toFixed(1)}%</strong>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Limitations Notice */}
          {response.limitations && response.limitations.length > 0 && (
            <div style={{ backgroundColor: '#fffbeb', border: '1px solid #fef3c7', borderRadius: '8px', padding: '12px 16px', fontSize: '13px', color: '#92400e' }}>
              <strong>Audit Limitations:</strong> {response.limitations.join('; ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
