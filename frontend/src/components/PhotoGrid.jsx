import React from 'react';

export default function PhotoGrid({ photos, onRemove }) {
  if (!photos || photos.length === 0) {
    return null;
  }

  return (
    <div>
      <p className="photo-count">{photos.length} photo(s) selected</p>
      <div className="photo-grid">
        {photos.map(photo => (
          <div key={photo.id} className="photo-thumbnail-container">
            <img src={photo.previewUrl} alt="Preview" className="photo-thumbnail" />
            <button 
              className="btn-remove-photo" 
              onClick={() => onRemove(photo.id)}
              aria-label="Remove photo"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
