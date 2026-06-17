export default function AnalyzeButton({ onClick, isLoading, disabled }) {
  return (
    <button 
      className="btn btn-primary" 
      onClick={onClick} 
      disabled={disabled || isLoading}
      style={{ marginTop: 'auto' }}
    >
      {isLoading ? (
        <>
          <div className="loading-spinner"></div>
          Analyzing inventory...
        </>
      ) : (
        'Analyze Freezer 🔍'
      )}
    </button>
  );
}
