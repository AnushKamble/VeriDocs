import React, { useState } from 'react';
import { ChunkRecord, RetrievalTrace } from '../types';
import { ExternalLink, Table, FileText, Activity, X } from 'lucide-react';

interface EvidenceInspectorProps {
  chunk: ChunkRecord | null;
  trace: RetrievalTrace | null;
  onClose: () => void;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({ chunk, trace, onClose }) => {
  const [tab, setTab] = useState<'content' | 'trace'>('content');

  if (!chunk && !trace) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      width: '540px',
      height: '100vh',
      backgroundColor: '#ffffff',
      boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      borderLeft: '1px solid #e2e8f0',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: '#f8fafc',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {chunk?.chunk_kind === 'table_group' || chunk?.chunk_kind === 'table_row' ? (
            <Table size={20} color="#2563eb" />
          ) : (
            <FileText size={20} color="#059669" />
          )}
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#0f172a' }}>
            Evidence Inspector
          </h3>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            color: '#64748b',
          }}
        >
          <X size={20} />
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', backgroundColor: '#f1f5f9' }}>
        <button
          onClick={() => setTab('content')}
          style={{
            flex: 1,
            padding: '10px',
            border: 'none',
            background: tab === 'content' ? '#ffffff' : 'transparent',
            borderBottom: tab === 'content' ? '2px solid #2563eb' : 'none',
            fontWeight: tab === 'content' ? 600 : 400,
            cursor: 'pointer',
            color: tab === 'content' ? '#2563eb' : '#64748b',
          }}
        >
          Filing Evidence
        </button>
        <button
          onClick={() => setTab('trace')}
          style={{
            flex: 1,
            padding: '10px',
            border: 'none',
            background: tab === 'trace' ? '#ffffff' : 'transparent',
            borderBottom: tab === 'trace' ? '2px solid #2563eb' : 'none',
            fontWeight: tab === 'trace' ? 600 : 400,
            cursor: 'pointer',
            color: tab === 'trace' ? '#2563eb' : '#64748b',
          }}
        >
          Retrieval Trace
        </button>
      </div>

      {/* Body */}
      <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
        {tab === 'content' && chunk && (
          <div>
            <div style={{ marginBottom: '16px', backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                Chunk Identifier: <code style={{ color: '#2563eb' }}>{chunk.chunk_id}</code>
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                Document: {chunk.document_id} | Section: {chunk.section_id} ({chunk.section_title})
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                Type: <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{chunk.chunk_kind}</span> | Tokens: {chunk.token_count}
              </div>
              {chunk.source_url && (
                <a
                  href={chunk.source_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#2563eb', textDecoration: 'none', marginTop: '6px' }}
                >
                  View official filing on SEC EDGAR <ExternalLink size={12} />
                </a>
              )}
            </div>

            <div style={{ marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>
              Verbatim Excerpt:
            </div>
            <pre style={{
              backgroundColor: '#0f172a',
              color: '#f8fafc',
              padding: '14px',
              borderRadius: '8px',
              fontSize: '12px',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'Consolas, monospace',
            }}>
              {chunk.text}
            </pre>
          </div>
        )}

        {tab === 'trace' && trace && (
          <div>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>
                <Activity size={16} color="#2563eb" /> Execution Timings
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {Object.entries(trace.timings_ms).map(([stage, ms]) => (
                  <div key={stage} style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', padding: '8px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>{stage.replace('_ms', '')}</div>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>{ms.toFixed(1)} ms</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>
                Retrieved Candidates Pool ({trace.fused_candidates.length || trace.bm25_candidates.length} items)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {(trace.reranked_candidates.length > 0 ? trace.reranked_candidates : trace.fused_candidates).map((c, i) => (
                  <div key={c.chunk_id} style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                    backgroundColor: i < 3 ? '#eff6ff' : '#f8fafc',
                    fontSize: '12px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                      <span style={{ fontWeight: 600, color: '#1e293b' }}>Rank #{c.rank + 1}: {c.chunk_id.slice(0, 24)}...</span>
                      <span style={{ color: '#2563eb', fontWeight: 600 }}>Score: {c.raw_score.toFixed(4)}</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Retriever: {c.retriever}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
