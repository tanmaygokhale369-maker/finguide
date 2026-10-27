export function ErrorState({ error, onRetry }) {
  const message = error?.message || 'Something went wrong.'

  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
