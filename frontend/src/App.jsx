import { useState } from 'react';
import CameraCapture from './components/CameraCapture';
import GalleryUpload from './components/GalleryUpload';
import PhotoGrid from './components/PhotoGrid';
import AnalyzeButton from './components/AnalyzeButton';
import ReportDisplay from './components/ReportDisplay';
import HistoryView from './components/HistoryView';
import { analyzeFreezer } from './api/client';

export default function App() {
  const [photos, setPhotos] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  const handlePhotosAdded = (newPhotos) => {
    setPhotos(prev => [...prev, ...newPhotos]);
    if (error) setError(null);
  };

  const handleRemovePhoto = (idToRemove) => {
    setPhotos(prev => prev.filter(photo => photo.id !== idToRemove));
  };

  const handleAnalyze = async () => {
    if (photos.length === 0 || isAnalyzing) return;
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeFreezer(photos);
      setReportData(result);
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? 'Could not reach server. Check WiFi connection.'
          : err.message || 'Could not analyze photos. Please try again.'
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleReset = () => {
    photos.forEach(photo => URL.revokeObjectURL(photo.previewUrl));
    setPhotos([]);
    setReportData(null);
    setError(null);
  };

  if (showHistory) {
    return (
      <div className="app-container">
        <h1>🧊 Ice Cream Inventory</h1>
        <HistoryView onClose={() => setShowHistory(false)} />
      </div>
    );
  }

  return (
    <div className="app-container">
      <h1>🧊 Ice Cream Inventory</h1>

      {!reportData ? (
        <>
          <div className="action-buttons">
            <CameraCapture onPhotosAdded={handlePhotosAdded} />
            <GalleryUpload onPhotosAdded={handlePhotosAdded} />
          </div>

          <PhotoGrid photos={photos} onRemove={handleRemovePhoto} />

          {error && (
            <div className="card error-card">
              <p>⚠️ {error}</p>
              <button
                className="btn btn-secondary"
                onClick={() => setError(null)}
                style={{ minHeight: '40px', padding: '0.5rem' }}
              >
                Dismiss
              </button>
            </div>
          )}

          <AnalyzeButton
            onClick={handleAnalyze}
            isLoading={isAnalyzing}
            disabled={photos.length === 0}
          />

          <button
            className="btn btn-secondary"
            style={{ marginTop: '0.75rem' }}
            onClick={() => setShowHistory(true)}
          >
            📋 View Scan History
          </button>
        </>
      ) : (
        <ReportDisplay reportData={reportData} onReset={handleReset} />
      )}
    </div>
  );
}
