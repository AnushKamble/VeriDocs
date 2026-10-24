import { useState, useEffect } from 'react';

interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

interface ModelStatus {
  generator: {
    provider: string;
    configured_model: string;
    available: boolean;
    installed_models: string[];
  };
  retrieval: {
    embedding_model_id: string;
    reranker_model_id: string;
    faiss_installed: boolean;
  };
  auditor: {
    nli_model_id: string;
  };
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [models, setModels] = useState<ModelStatus | null>(null);
  const [activeTab, setActiveTab] = useState<'research' | 'evidence' | 'ingestion' | 'eval'>('research');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        setLoading(true);
        const [hRes, mRes] = await Promise.all([
          fetch('/api/v1/health'),
          fetch('/api/v1/models/status')
        ]);
        if (hRes.ok) {
          setHealth(await hRes.json());
        }
        if (mRes.ok) {
          setModels(await mRes.json());
        }
      } catch (err: any) {
        setError(err.message || 'Failed to connect to backend server');
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <header style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '16px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700, color: '#1e293b' }}>
              VeriDocs
            </h1>
            <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '0.95rem' }}>
              Grounded Financial Intelligence Engine for SEC 10-K / 10-Q Filings
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: health?.status === 'healthy' ? '#dcfce7' : '#fee2e2',
              color: health?.status === 'healthy' ? '#166534' : '#991b1b',
            }}>
              API: {health ? health.status : (loading ? 'Checking...' : 'Offline')}
            </span>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: models?.generator.available ? '#dcfce7' : '#fef9c3',
              color: models?.generator.available ? '#166534' : '#854d0e',
            }}>
              Ollama: {models?.generator.available ? models.generator.configured_model : 'Not Detected'}
            </span>
          </div>
        </div>

        <nav style={{ display: 'flex', gap: '8px', marginTop: '20px' }}>
          {(['research', 'evidence', 'ingestion', 'eval'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                backgroundColor: activeTab === tab ? '#2563eb' : '#f1f5f9',
                color: activeTab === tab ? '#ffffff' : '#475569',
                border: 'none',
                fontWeight: 600,
                textTransform: 'capitalize',
              }}
            >
              {tab === 'eval' ? 'Evaluation & Benchmarks' : tab}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {error && (
          <div style={{ backgroundColor: '#fee2e2', color: '#991b1b', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px' }}>
            <strong>Connection Warning:</strong> {error}
          </div>
        )}

        <div style={{ backgroundColor: '#ffffff', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          {activeTab === 'research' && (
            <div>
              <h2 style={{ marginTop: 0, fontSize: '1.25rem', color: '#1e293b' }}>Financial Research Workspace</h2>
              <p style={{ color: '#64748b' }}>
                Ask targeted financial questions over ingested 10-K/10-Q filings with table-aware chunking, hybrid retrieval, and claim-level NLI auditing.
              </p>
              <div style={{ marginTop: '16px', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <p style={{ margin: 0, color: '#475569', fontSize: '0.9rem' }}>
                  <strong>System Ready.</strong> Proceed to Ingestion tab to load filings, or execute questions once indexed.
                </p>
              </div>
            </div>
          )}

          {activeTab === 'evidence' && (
            <div>
              <h2 style={{ marginTop: 0, fontSize: '1.25rem', color: '#1e293b' }}>Evidence Inspector</h2>
              <p style={{ color: '#64748b' }}>
                Inspect parsed tabular context, column header paths, accounting parenthetical values, and raw source excerpts.
              </p>
            </div>
          )}

          {activeTab === 'ingestion' && (
            <div>
              <h2 style={{ marginTop: 0, fontSize: '1.25rem', color: '#1e293b' }}>Filing Ingestion & Catalog</h2>
              <p style={{ color: '#64748b' }}>
                Discover public 10-K and 10-Q filings from SEC EDGAR with rate-limited polite fetching and idempotent persistence.
              </p>
            </div>
          )}

          {activeTab === 'eval' && (
            <div>
              <h2 style={{ marginTop: 0, fontSize: '1.25rem', color: '#1e293b' }}>Evaluation & Benchmark Suite</h2>
              <p style={{ color: '#64748b' }}>
                Reproducible 50-question held-out benchmark comparing BM25, Dense, Hybrid RRF, Cross-Encoder Reranking, and Claim Auditing.
              </p>
            </div>
          )}
        </div>
      </main>

      <footer style={{ marginTop: '40px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', color: '#94a3b8', fontSize: '0.85rem', textAlign: 'center' }}>
        VeriDocs Grounded Financial Intelligence Engine — Independent Audit & Research System
      </footer>
    </div>
  );
}
