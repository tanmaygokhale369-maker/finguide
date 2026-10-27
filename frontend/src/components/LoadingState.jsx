export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="state state-loading" role="status">
      {label}
    </div>
  )
}
