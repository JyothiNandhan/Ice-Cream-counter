export default function CameraCapture({ onPhotosAdded }) {
  const handleChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newPhotos = Array.from(e.target.files).map(file => ({
        id: Math.random().toString(36).substring(7),
        file,
        previewUrl: URL.createObjectURL(file)
      }));
      onPhotosAdded(newPhotos);
    }
    // Reset input so taking another photo works
    e.target.value = null;
  };

  return (
    <div className="action-btn-container">
      <button className="btn btn-primary">
        <span>📷</span> Take Photo
      </button>
      <input 
        type="file" 
        accept="image/*" 
        capture="environment" 
        className="file-input"
        onChange={handleChange}
      />
    </div>
  );
}
