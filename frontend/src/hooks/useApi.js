import { useEffect, useState } from 'react'

/**
 * Runs an API call and exposes { data, loading, error }.
 *
 * `fetcher` must be a function returning a promise (typically an
 * `apiClient` call). Pass a stable `deps` array like `useEffect` if the
 * call depends on changing values.
 *
 * This keeps the loading/error UI pattern identical across pages instead
 * of every page re-implementing its own fetch/try/catch/state trio.
 */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)

    fetcher({ signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setData(result)
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, retryCount])

  const refetch = () => setRetryCount((count) => count + 1)

  return { data, loading, error, refetch }
}
