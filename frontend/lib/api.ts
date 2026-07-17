import axios from 'axios'

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
})

export function getSessionValue(key: string): string | null {
  if (typeof window === 'undefined') return null
  try {
    // Session storage clears automatically when the browser session ends.
    return sessionStorage.getItem(key) || localStorage.getItem(key)
  } catch {
    return null
  }
}

export function clearSession(): void {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('user')
    // Clear legacy demo values too; fabricated client-side tokens are invalid.
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  } catch {
    // Browsers with storage disabled simply remain unauthenticated.
  }
}

// Add only an opaque server-issued bearer token to requests.  No credentials
// are put in URLs, logs, or browser-persistent storage.
API.interceptors.request.use((config) => {
  const token = getSessionValue('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default API
