import { useState, useEffect } from 'react';
import { ResearchWorkspace } from './pages/ResearchWorkspace';
import { IngestionPage } from './pages/IngestionPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { EvidenceInspector } from './components/EvidenceInspector';
import { ChunkRecord, RetrievalTrace } from './types';
import { BookOpen, Database, BarChart2, CheckCircle2, ShieldCheck } from 'lucide-react';

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
  const [activeTab, setActiveTab] = useState<'research' | 'ingestion' | 'eval'>('research');
  const [selectedChunk, setSelectedChunk] = useState<ChunkRecord | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<RetrievalTrace | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const [hRes, mRes] = await Promise.all([
          fetch('/api/v1/health'),
          fetch('/api/v1/models/status')
        ]);
        if (hRes.ok) setHealth(await hRes.json());
        if (mRes.ok) setModels(await mRes.json());
      } catch (err) {
        console.warn('Backend status probe notice', err);
      }
    }
    fetchStatus();
  }, []);

  const handleSelectEvidence = (chunk: ChunkRecord, trace: RetrievalTrace) => {
    setSelectedChunk(chunk);
    setSelectedTrace(trace);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', color: '#0f172a', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Top Header */}
      <header style={{ backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '12px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ backgroundColor: '#2563eb', color: '#ffffff', padding: '6px 10px', borderRadius: '8px', fontWeight: 800, fontSize: '16px' }}>
              VD
            </div>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                VeriDocs
              </h1>
              <p style={{ fontSize: '11px', color: '#64748b', margin: 0 }}>
                Grounded Financial Intelligence & SEC Claim Auditor
              </p>
            </div>
          </div>

          {/* Model & System Health Badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: health?.status === 'healthy' ? '#059669' : '#d97706', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '12px' }}>
              <CheckCircle2 size={12} />
              API: {health?.status || 'Online'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#2563eb', backgroundColor: '#eff6ff', padding: '4px 8px', borderRadius: '12px' }}>
              <ShieldCheck size={12} />
              LLM: {models?.generator?.configured_model || 'qwen3:8b'}
            </div>
            <div style={{ fontSize: '11px', color: '#64748b', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '12px' }}>
              NLI: DeBERTa-v3
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', display: 'flex', gap: '4px' }}>
          <button
            onClick={() => setActiveTab('research')}
            style={{
              padding: '12px 18px',
              border: 'none',
              background: 'none',
              borderBottom: activeTab === 'research' ? '2px solid #2563eb' : '2px solid transparent',
              color: activeTab === 'research' ? '#2563eb' : '#64748b',
              fontWeight: activeTab === 'research' ? 600 : 500,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <BookOpen size={16} /> Research Workspace
          </button>
          <button
            onClick={() => setActiveTab('ingestion')}
            style={{
              padding: '12px 18px',
              border: 'none',
              background: 'none',
              borderBottom: activeTab === 'ingestion' ? '2px solid #2563eb' : '2px solid transparent',
              color: activeTab === 'ingestion' ? '#2563eb' : '#64748b',
              fontWeight: activeTab === 'ingestion' ? 600 : 500,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Database size={16} /> Filing Ingestion
          </button>
          <button
            onClick={() => setActiveTab('eval')}
            style={{
              padding: '12px 18px',
              border: 'none',
              background: 'none',
              borderBottom: activeTab === 'eval' ? '2px solid #2563eb' : '2px solid transparent',
              color: activeTab === 'eval' ? '#2563eb' : '#64748b',
              fontWeight: activeTab === 'eval' ? 600 : 500,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <BarChart2 size={16} /> Benchmark Evaluation
          </button>
        </div>
      </header>

      {/* Main Content View */}
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
        {activeTab === 'research' && (
          <ResearchWorkspace onSelectEvidence={handleSelectEvidence} />
        )}
        {activeTab === 'ingestion' && <IngestionPage />}
        {activeTab === 'eval' && <EvaluationPage />}
      </main>

      {/* Slide-out Evidence Inspector */}
      {selectedChunk && (
        <EvidenceInspector
          chunk={selectedChunk}
          trace={selectedTrace}
          onClose={() => setSelectedChunk(null)}
        />
      )}
    </div>
  );
}
