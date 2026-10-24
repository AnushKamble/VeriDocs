import React, { useState, useEffect } from 'react';
import { CheckCircle, HelpCircle, Filter } from 'lucide-react';

export const EvaluationPage: React.FC = () => {
  const [manifest, setManifest] = useState<any>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [activeSplit, setActiveSplit] = useState<string>('all');
  const [activeCategory, setActiveCategory] = useState<string>('all');

  useEffect(() => {
    async function loadBenchmarkData() {
      try {
        const [mRes, qRes] = await Promise.all([
          fetch('/api/v1/evaluation/benchmark'),
          fetch('/api/v1/evaluation/benchmark/questions'),
        ]);

        if (mRes.ok) {
          const mData = await mRes.json();
          setManifest(mData);
        }
        if (qRes.ok) {
          const qData = await qRes.json();
          setQuestions(qData || []);
        }
      } catch (err) {
        console.error('Failed to load benchmark data', err);
      }
    }
    loadBenchmarkData();
  }, []);


  const filteredQuestions = questions.filter((q) => {
    if (activeSplit !== 'all') {
      if (manifest?.splits?.[activeSplit]) {
        const allowedIds = new Set(manifest.splits[activeSplit]);
        if (!allowedIds.has(q.question_id)) return false;
      }
    }
    if (activeCategory !== 'all' && q.category !== activeCategory) {
      return false;
    }
    return true;
  });

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>
      {/* Overview Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Benchmark Suite</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', marginTop: '4px' }}>
            {manifest?.manifest?.benchmark_name || 'VeriDocs-SEC-50'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>v{manifest?.manifest?.version || '1.0.0'}</div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Total Questions</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#2563eb', marginTop: '4px' }}>
            {manifest?.manifest?.total_questions || 50}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>100% Grounded in 10-K/Q</div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Dev / Calibration</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#059669', marginTop: '4px' }}>
            {manifest?.splits?.dev?.length || 15} questions
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Pre-frozen thresholds</div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Held-Out Test</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#7c3aed', marginTop: '4px' }}>
            {manifest?.splits?.test?.length || 35} questions
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Zero-leakage test set</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '14px 16px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Filter size={16} color="#64748b" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b' }}>Split:</span>
          {['all', 'dev', 'test'].map((s) => (
            <button
              key={s}
              onClick={() => setActiveSplit(s)}
              style={{
                padding: '4px 12px',
                borderRadius: '16px',
                border: '1px solid',
                borderColor: activeSplit === s ? '#2563eb' : '#e2e8f0',
                backgroundColor: activeSplit === s ? '#eff6ff' : '#ffffff',
                color: activeSplit === s ? '#2563eb' : '#475569',
                fontSize: '12px',
                fontWeight: activeSplit === s ? 600 : 400,
                cursor: 'pointer',
                textTransform: 'uppercase',
              }}
            >
              {s}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b' }}>Category:</span>
          <select
            value={activeCategory}
            onChange={(e) => setActiveCategory(e.target.value)}
            style={{ padding: '4px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
          >
            <option value="all">All Categories (8)</option>
            <option value="numeric_table_lookup">Numeric Table Lookup</option>
            <option value="period_comparison">Period Comparison</option>
            <option value="units_sign_edge_case">Units & Sign Edge Case</option>
            <option value="narrative_mda">Narrative MD&A</option>
            <option value="multi_evidence">Multi-Evidence</option>
            <option value="unanswerable">Unanswerable / Abstention</option>
            <option value="ambiguous_period">Ambiguous Period</option>
            <option value="conflicting">Conflicting Evidence</option>
          </select>
        </div>
      </div>

      {/* Questions List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {filteredQuestions.map((q) => (
          <div key={q.question_id} style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '16px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#2563eb', backgroundColor: '#eff6ff', padding: '2px 8px', borderRadius: '4px' }}>
                  {q.question_id.toUpperCase()}
                </span>
                <span style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a' }}>
                  {q.ticker} ({q.form_type} {q.fiscal_period})
                </span>
                <span style={{ fontSize: '11px', color: '#64748b', backgroundColor: '#f1f5f9', padding: '2px 8px', borderRadius: '12px' }}>
                  {q.category}
                </span>
              </div>
              <div>
                {q.is_answerable ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '11px', color: '#059669', fontWeight: 600 }}>
                    <CheckCircle size={12} /> Answerable
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '11px', color: '#d97706', fontWeight: 600 }}>
                    <HelpCircle size={12} /> Must Abstain
                  </span>
                )}
              </div>
            </div>

            <div style={{ fontSize: '14px', fontWeight: 500, color: '#1e293b', marginBottom: '8px' }}>
              {q.question_text}
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', color: '#334155', border: '1px solid #e2e8f0' }}>
              <strong>Reference Answer:</strong> {q.reference_answer}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
