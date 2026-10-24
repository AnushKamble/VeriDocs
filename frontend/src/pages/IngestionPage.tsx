import React, { useState, useEffect } from 'react';
import { FilingDocument } from '../types';
import { Database, Download, Search, CheckCircle, RefreshCw, FileCode } from 'lucide-react';

export const IngestionPage: React.FC = () => {
  const [ticker, setTicker] = useState('AAPL');
  const [formType, setFormType] = useState('10-K');
  const [discoveredFilings, setDiscoveredFilings] = useState<any[]>([]);
  const [catalogFilings, setCatalogFilings] = useState<FilingDocument[]>([]);
  const [loadingDiscovery, setLoadingDiscovery] = useState(false);
  const [ingestingAccession, setIngestingAccession] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Direct HTML upload tab
  const [showCustomHtml, setShowCustomHtml] = useState(false);
  const [customTicker, setCustomTicker] = useState('AAPL');
  const [customHtml, setCustomHtml] = useState('');

  const fetchCatalog = async () => {
    try {
      const res = await fetch('/api/v1/filings');
      if (res.ok) {
        const data = await res.json();
        setCatalogFilings(data.filings || []);
      }
    } catch (e) {
      console.error('Failed to load catalog', e);
    }
  };

  useEffect(() => {
    fetchCatalog();
  }, []);

  const handleDiscover = async () => {
    if (!ticker.trim()) return;
    setLoadingDiscovery(true);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/filings/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker.trim(), form_types: [formType], limit: 5 }),
      });
      if (!res.ok) throw new Error('SEC discovery request failed');
      const data = await res.json();
      setDiscoveredFilings(data.filings || []);
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setLoadingDiscovery(false);
    }
  };

  const handleIngest = async (filing: any) => {
    setIngestingAccession(filing.accession_number);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/filings/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: filing.ticker || ticker,
          cik: filing.cik,
          form_type: filing.form_type,
          accession_number: filing.accession_number,
          primary_document_name: filing.primary_document_name,
          source_url: filing.source_url,
        }),
      });
      if (!res.ok) throw new Error('Ingestion failed');
      const manifest = await res.json();
      setMessage({
        text: `Successfully ingested ${filing.form_type} (${manifest.document_id})! Generated ${manifest.chunk_count} chunks across ${manifest.table_count} tables.`,
        type: 'success',
      });
      await fetchCatalog();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setIngestingAccession(null);
    }
  };

  const handleCustomIngest = async () => {
    if (!customHtml.trim()) return;
    setIngestingAccession('custom');
    setMessage(null);
    try {
      const res = await fetch('/api/v1/filings/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: customTicker,
          form_type: '10-K',
          raw_html: customHtml,
        }),
      });
      if (!res.ok) throw new Error('Custom HTML ingestion failed');
      const manifest = await res.json();
      setMessage({
        text: `Custom filing parsed and cataloged! ${manifest.chunk_count} chunks stored.`,
        type: 'success',
      });
      setCustomHtml('');
      await fetchCatalog();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setIngestingAccession(null);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#0f172a', margin: '0 0 4px 0' }}>
            SEC Filing Ingestion & Provenance Catalog
          </h2>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Discover official SEC 10-K/10-Q corporate filings, parse tables into 2D grids, and catalog index artifacts.
          </p>
        </div>
        <button
          onClick={() => setShowCustomHtml(!showCustomHtml)}
          style={{
            padding: '8px 14px',
            backgroundColor: showCustomHtml ? '#eff6ff' : '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: '6px',
            fontSize: '12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <FileCode size={16} /> Direct HTML Paste
        </button>
      </div>

      {message && (
        <div style={{
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '20px',
          fontSize: '13px',
          backgroundColor: message.type === 'success' ? '#ecfdf5' : '#fef2f2',
          color: message.type === 'success' ? '#065f46' : '#991b1b',
          border: `1px solid ${message.type === 'success' ? '#a7f3d0' : '#fecaca'}`,
        }}>
          {message.text}
        </div>
      )}

      {/* Custom HTML Form */}
      {showCustomHtml && (
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px', marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#0f172a' }}>Direct Filing HTML Input</h4>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
            <input
              type="text"
              placeholder="Ticker (e.g. AAPL)"
              value={customTicker}
              onChange={(e) => setCustomTicker(e.target.value.toUpperCase())}
              style={{ width: '120px', padding: '8px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
            />
            <button
              onClick={handleCustomIngest}
              disabled={ingestingAccession === 'custom'}
              style={{ padding: '8px 16px', backgroundColor: '#059669', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
            >
              {ingestingAccession === 'custom' ? 'Ingesting...' : 'Parse & Catalog HTML'}
            </button>
          </div>
          <textarea
            rows={6}
            placeholder="Paste raw 10-K / 10-Q HTML markup with tables here..."
            value={customHtml}
            onChange={(e) => setCustomHtml(e.target.value)}
            style={{ width: '100%', boxSizing: 'border-box', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontFamily: 'Consolas, monospace', fontSize: '12px' }}
          />
        </div>
      )}

      {/* Discovery Tool */}
      <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px', marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#0f172a' }}>Discover Filings on SEC EDGAR</h4>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
          <input
            type="text"
            placeholder="Ticker or CIK (e.g. AAPL, MSFT, 0000320193)"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            style={{ flex: 1, padding: '10px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px' }}
          />
          <select
            value={formType}
            onChange={(e) => setFormType(e.target.value)}
            style={{ padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px' }}
          >
            <option value="10-K">Form 10-K (Annual)</option>
            <option value="10-Q">Form 10-Q (Quarterly)</option>
          </select>
          <button
            onClick={handleDiscover}
            disabled={loadingDiscovery}
            style={{
              padding: '10px 20px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              cursor: loadingDiscovery ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Search size={16} /> {loadingDiscovery ? 'Discovering...' : 'Discover'}
          </button>
        </div>

        {/* Discovered List */}
        {discoveredFilings.length > 0 && (
          <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '12px' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', marginBottom: '8px' }}>
              DISCOVERED OFFICIAL SEC FILINGS:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {discoveredFilings.map((f, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '13px' }}>
                  <div>
                    <span style={{ fontWeight: 600, color: '#0f172a' }}>{f.form_type}</span> — Period: {f.report_period} | Date: {f.filing_date} | Accession: <code style={{ fontSize: '11px' }}>{f.accession_number}</code>
                  </div>
                  <button
                    onClick={() => handleIngest(f)}
                    disabled={ingestingAccession === f.accession_number}
                    style={{
                      padding: '6px 14px',
                      backgroundColor: '#2563eb',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: ingestingAccession === f.accession_number ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <Download size={14} /> {ingestingAccession === f.accession_number ? 'Ingesting...' : 'Ingest & Index'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Catalog Table */}
      <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={18} color="#2563eb" />
            <h4 style={{ margin: 0, fontSize: '15px', color: '#0f172a' }}>
              Persisted Document Catalog ({catalogFilings.length} filings)
            </h4>
          </div>
          <button
            onClick={fetchCatalog}
            style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {catalogFilings.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '14px' }}>
            No filings have been cataloged yet. Use the discovery tool above to ingest SEC filings.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                <th style={{ padding: '10px' }}>Ticker</th>
                <th style={{ padding: '10px' }}>Form</th>
                <th style={{ padding: '10px' }}>Filing Date</th>
                <th style={{ padding: '10px' }}>Period</th>
                <th style={{ padding: '10px' }}>Document ID</th>
                <th style={{ padding: '10px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {catalogFilings.map((doc) => (
                <tr key={doc.document_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '10px', fontWeight: 600 }}>{doc.ticker || 'N/A'}</td>
                  <td style={{ padding: '10px' }}>{doc.form_type}</td>
                  <td style={{ padding: '10px' }}>{doc.filing_date}</td>
                  <td style={{ padding: '10px' }}>{doc.report_period}</td>
                  <td style={{ padding: '10px' }}><code style={{ fontSize: '11px', color: '#64748b' }}>{doc.document_id}</code></td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#166534', backgroundColor: '#dcfce7', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600 }}>
                      <CheckCircle size={10} /> {doc.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
