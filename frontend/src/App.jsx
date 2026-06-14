import React, { useState } from 'react';
import CameraCapture from './components/CameraCapture';
import GalleryUpload from './components/GalleryUpload';
import PhotoGrid from './components/PhotoGrid';
import AnalyzeButton from './components/AnalyzeButton';
import ReportDisplay from './components/ReportDisplay';
import { analyzeFreezer } from './api/client';

export default function App() {
  const [photos, setPhotos] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);

  const handlePhotosAdded = (newPhotos) => {
    setPhotos(prev => [...prev, ...newPhotos]);
    // Clear errors when new photos are added
    if (error) setError(null);
  };

  const handleRemovePhoto = (idToRemove) => {
    setPhotos(prev => prev.filter(photo => photo.id !== idToRemove));
  };

  const handleAnalyze = async () => {
    if (photos.length === 0) return;
    
    setIsAnalyzing(true);
    setError(null);
    
    try {
      const result = await analyzeFreezer(photos);
      setReportData(result);
    } catch (err) {
      if (err.message === 'Failed to fetch') {
        setError('Could not reach server. Check WiFi connection.');
      } else {
        setError(err.message || 'Could not analyze photos. Please try again.');
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleReset = () => {
    // Revoke object URLs to avoid memory leaks
    photos.forEach(photo => URL.revokeObjectURL(photo.previewUrl));
    setPhotos([]);
    setReportData(null);
    setError(null);
  };

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
              <button className="btn btn-secondary" onClick={() => setError(null)} style={{minHeight: '40px', padding: '0.5rem'}}>
                Dismiss
              </button>
            </div>
          )}

          <AnalyzeButton 
            onClick={handleAnalyze} 
            isLoading={isAnalyzing} 
            disabled={photos.length === 0} 
          />
        </>
      ) : (
        <ReportDisplay reportData={reportData} onReset={handleReset} />
      )}
    </div>
  );
}
