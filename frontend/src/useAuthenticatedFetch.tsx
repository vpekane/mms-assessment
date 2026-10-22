import { useCallback } from 'react'
import { useAuth } from '@clerk/react'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5000'

export function useAuthenticatedFetch() {
  const { getToken, isLoaded, isSignedIn } = useAuth()

  return useCallback(
    async (path: string, init: RequestInit = {}) => {
      if (!isLoaded || !isSignedIn) {
        throw new Error('You must be signed in to access Sentinel.')
      }

      const token = await getToken()

      if (!token) {
        throw new Error('Clerk did not provide a session token.')
      }

      const headers = new Headers(init.headers)
      headers.set('Authorization', `Bearer ${token}`)

      const url = `${API_BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`

      return fetch(url, {
        ...init,
        headers,
      })
    },
    [getToken, isLoaded, isSignedIn],
  )
}