const TOKEN_KEY = 'pitwall_token'

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export const setToken = (t) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export async function api(path, { method = 'GET', body, params } = {}) {
  let url = `${API_BASE}/api${path}`
  if (params) {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '' && v !== false) q.set(k, Array.isArray(v) ? v.join(',') : v)
    })
    const s = q.toString()
    if (s) url += `?${s}`
  }
  const headers = { 'Content-Type': 'application/json' }
  const t = getToken()
  if (t) headers.Authorization = `Bearer ${t}`
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined })
  let data = null
  try { data = await res.json() } catch { /* empty */ }
  if (!res.ok) {
    const msg = typeof data?.detail === 'string' ? data.detail : (data?.detail?.[0]?.msg || `Request failed (${res.status})`)
    if (res.status === 401 && t) { setToken(null); window.dispatchEvent(new Event('pitwall:logout')) }
    throw new ApiError(msg, res.status)
  }
  return data
}
