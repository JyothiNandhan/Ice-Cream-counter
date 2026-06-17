import { useEffect, useState } from 'react';
import { getHistory } from '../api/client';

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function HistoryView({ onClose }) {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getHistory(20)
      .then(data => setScans(data.scans))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="history-header">
        <h2>Scan History</h2>
        <button
          className="btn btn-secondary"
          style={{ width: 'auto', padding: '0.4rem 1rem', minHeight: '36px' }}
          onClick={onClose}
        >
          ← Back
        </button>
      </div>

      {loading && <p className="photo-count">Loading history...</p>}
      {error && <p style={{ color: 'var(--error-color)' }}>⚠️ {error}</p>}
      {!loading && !error && scans.length === 0 && (
        <p className="photo-count">No scans yet. Take your first photo!</p>
      )}

      {scans.map(scan => (
        <div
          key={scan.id}
          className="card history-card"
          onClick={() => setExpanded(expanded === scan.id ? null : scan.id)}
        >
          <div className="brand-header">
            <div>
              <p style={{ fontWeight: 600 }}>Scan #{scan.id}</p>
              <p className="units-sub">{formatDate(scan.timestamp)}</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p className="units-sub">~{scan.total_units} units · {scan.item_count} products</p>
              {scan.critical_count > 0 && (
                <span className="badge badge-CRITICAL">{scan.critical_count} critical</span>
              )}
            </div>
          </div>

          {expanded === scan.id && (
            <div className="history-expanded">
              {scan.report.length === 0 ? (
                <p className="units-sub">No report data for this scan.</p>
              ) : (
                scan.report.map((item, idx) => (
                  <div key={idx} className="history-row">
                    <span>{item.brand} — {item.product_name}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className="units-sub">~{item.units_currently_visible}</span>
                      {item.fill_level && (
                        <span className={`badge badge-${item.fill_level}`}>{item.fill_level}</span>
                      )}
                      <span className={`badge badge-${item.restock_urgency}`}>
                        {item.restock_urgency}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
