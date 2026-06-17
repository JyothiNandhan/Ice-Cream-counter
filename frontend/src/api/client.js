const handleErrorResponse = async (response) => {
  let message = "Could not reach server. Please try again.";
  try {
    const data = await response.json();
    if (data?.detail) message = data.detail;
  } catch (_) {}
  throw new Error(message);
};

export const analyzeFreezer = async (photos) => {
  const formData = new FormData();
  photos.forEach((photo) => formData.append('images', photo.file));

  const response = await fetch('/api/analyze', { method: 'POST', body: formData });
  if (!response.ok) await handleErrorResponse(response);
  return response.json();
};

export const getHistory = async (limit = 20) => {
  const response = await fetch(`/api/history?limit=${limit}`);
  if (!response.ok) await handleErrorResponse(response);
  return response.json();
};
