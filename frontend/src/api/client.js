/**
 * Shared API service layer.
 *
 * Brick 02 scope: a thin, typed-by-convention wrapper around fetch so
 * pages never call `fetch` directly. Every request goes through here,
 * which is where later bricks add things like auth headers (Brick 19)
 * without touching page components.
 *
 * Feature-specific methods live below, grouped by their backend API
 * domains. Keeping requests centralized means cookie/session behavior
 * and shared error handling stay consistent across pages.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

async function request(path, { method = 'GET', body, headers, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      credentials: 'include',
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (networkError) {
    throw new ApiError('Unable to reach the FinGuide+ backend.', {
      status: null,
      data: networkError,
    })
  }

  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiError(
      typeof data === 'object' && data?.detail ? data.detail : `Request to ${path} failed (${response.status}).`,
      { status: response.status, data },
    )
  }

  return data
}

export const apiClient = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
}

/** Calls the Brick 01 health endpoint. */
export function getHealth(options) {
  return apiClient.get('/api/v1/health', options)
}

// --- Financial Profile (Brick 05) ---------------------------------------

export function getProfile(options) {
  return apiClient.get('/api/v1/profile', options)
}

export function createProfile(payload, options) {
  return apiClient.post('/api/v1/profile', payload, options)
}

export function updateProfile(payload, options) {
  return apiClient.patch('/api/v1/profile', payload, options)
}

/** Triggers a fresh Brick 09 metrics computation and returns the result. */
export function getProfileMetrics(options) {
  return apiClient.get('/api/v1/profile/metrics', options)
}

// --- Transactions (Brick 10) --------------------------------------------
export function listTransactions({ limit = 100, offset = 0, ...filters } = {}, options) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value)
  }
  return apiClient.get(`/api/v1/transactions?${params}`, options)
}
export function createTransaction(payload, options) {
  return apiClient.post('/api/v1/transactions', payload, options)
}
export function deleteTransaction(id, options) {
  return apiClient.delete(`/api/v1/transactions/${id}`, options)
}

// --- Chat (Brick 06) -----------------------------------------------------
export function sendChatMessage(payload, options) {
  return apiClient.post('/api/v1/chat', payload, options)
}
export function getConversation(id, options) {
  return apiClient.get(`/api/v1/chat/${id}`, options)
}
export function getChatCapabilities(options) {
  return apiClient.get('/api/v1/chat/capabilities', options)
}

// --- Recommendations (Bricks 12-14) --------------------------------------

export function listRecommendations(options) {
  return apiClient.get('/api/v1/recommendations', options)
}

export function generateRecommendations(options) {
  return apiClient.post('/api/v1/recommendations/generate', undefined, options)
}

export function evaluatePendingRecommendations(options) {
  return apiClient.post('/api/v1/recommendations/evaluate-pending', undefined, options)
}

export function evaluateRecommendation(id, options) {
  return apiClient.post(`/api/v1/recommendations/${id}/evaluate`, undefined, options)
}

export function getRecommendationExplanation(id, options) {
  return apiClient.get(`/api/v1/recommendations/${id}/explanation`, options)
}

/** Fetch a free-source, profile-gated mutual-fund research shortlist. */
export function getMarketResearchShortlist(options) {
  return apiClient.get('/api/v1/market-research/shortlist', options)
}
export function getFundAnalysis(schemeCode, options) {
  return apiClient.get(`/api/v1/market-research/funds/${schemeCode}/analysis`, options)
}
export function getOfficialFinancialUpdates(options) {
  return apiClient.get('/api/v1/news/official-updates', options)
}

/** Build a goal savings baseline and screen current MF research by goal horizon. */
export function createMutualFundGoalPlan(payload, options) {
  return apiClient.post('/api/v1/market-research/plan', payload, options)
}

// --- Mutual-fund holdings ------------------------------------------------
export function searchFundSchemes(query, options) {
  return apiClient.get(`/api/v1/holdings/schemes?q=${encodeURIComponent(query)}`, options)
}
export function listHoldings(options) {
  return apiClient.get('/api/v1/holdings', options)
}
export function createHolding(payload, options) {
  return apiClient.post('/api/v1/holdings', payload, options)
}
export function updateHolding(id, payload, options) {
  return apiClient.patch(`/api/v1/holdings/${id}`, payload, options)
}
export function listHoldingActivity(id, options) {
  return apiClient.get(`/api/v1/holdings/${id}/activity`, options)
}
export function createHoldingActivity(id, payload, options) {
  return apiClient.post(`/api/v1/holdings/${id}/activity`, payload, options)
}
export function deleteHoldingActivity(id, activityId, options) {
  return apiClient.delete(`/api/v1/holdings/${id}/activity/${activityId}`, options)
}
export function deleteHolding(id, options) {
  return apiClient.delete(`/api/v1/holdings/${id}`, options)
}

// --- Authentication and Brick 18 lifecycle -----------------------------
export function register(payload, options) {
  return apiClient.post('/api/v1/auth/register', payload, options)
}
export function login(payload, options) {
  return apiClient.post('/api/v1/auth/login', payload, options)
}
export function logout(options) {
  return apiClient.post('/api/v1/auth/logout', undefined, options)
}
export function presentRecommendation(id, options) {
  return apiClient.post(`/api/v1/recommendations/${id}/present`, undefined, options)
}
export function submitRecommendationFeedback(id, payload, options) {
  return apiClient.post(`/api/v1/recommendations/${id}/feedback`, payload, options)
}
export function recordConsent(payload, options) {
  return apiClient.post('/api/v1/privacy/consent', payload, options)
}
export function getConsentRecords(options) {
  return apiClient.get('/api/v1/privacy/consent', options)
}
export function exportUserData(options) {
  return apiClient.get('/api/v1/privacy/export', options)
}
