import React from 'react';

export default function ReportDisplay({ reportData, onReset }) {
  if (!reportData) return null;

  const { report, whatsapp_statuses } = reportData;

  return (
    <div>
      <h2 className="report-header">✅ Analysis Complete</h2>
      
      {report.map((item, idx) => (
        <div key={idx} className="card brand-card">
          <div className="brand-header">
            <h3>{item.brand} — <span style={{fontWeight: 'normal'}}>{item.product_name}</span></h3>
            <span className={`badge badge-${item.restock_urgency}`}>
              {item.restock_urgency}
            </span>
          </div>
          
          <div className="units-display">
            <div>
              <span className="units-large">{item.units_currently_visible}</span>
              <span className="units-sub"> / {item.shelf_capacity_estimate} max</span>
            </div>
            {item.units_sold !== null && (
              <div className="units-sub" style={{textAlign: 'right'}}>
                {item.units_sold} sold since last scan
              </div>
            )}
          </div>
        </div>
      ))}

      <div className="whatsapp-section">
        <h3>📱 WhatsApp Report Sent</h3>
        <ul className="whatsapp-list">
          {whatsapp_statuses.map((status, idx) => (
            <li key={idx}>
              <span className="status-icon">
                {status.success ? '✅' : '❌'}
              </span>
              <span>{status.number}</span>
              {!status.success && (
                <span style={{color: 'var(--error-color)', fontSize: '0.8rem', marginLeft: 'auto'}}>
                  Failed
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <button className="btn btn-secondary" onClick={onReset}>
          Scan Again
        </button>
      </div>
    </div>
  );
}
