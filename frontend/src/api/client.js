export const analyzeFreezer = async (photos) => {
  const formData = new FormData();
  
  photos.forEach((photo) => {
    formData.append('images', photo.file);
  });
  
  // Notice we use the relative path, Vite proxy handles routing to :8000
  const response = await fetch('/api/analyze', {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    let errorMessage = "Could not analyze photos. Please try again.";
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch (e) {
      // If parsing fails, fall back to default error
    }
    throw new Error(errorMessage);
  }
  
  return await response.json();
};
