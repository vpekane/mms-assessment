import { useState } from 'react'
import { useAuthenticatedFetch } from './useAuthenticatedFetch'

interface MeResponse {
  user_id?: string
  error?: string
  description?: string
  details?: string
}

export default function BackendAuthCheck() {
  const authenticatedFetch = useAuthenticatedFetch()

  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function checkBackendAuthentication() {
    setLoading(true)
    setMessage('')

    try {
      const response = await authenticatedFetch('/me')
      const data = (await response.json()) as MeResponse

      if (!response.ok) {
        throw new Error(
        data.details ??
        data.description ??
        data.error ??
        `Request failed with status ${response.status}`,
        )
        }

      setMessage(`Backend authenticated user: ${data.user_id}`)
    } catch (error: unknown) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'An unexpected error occurred.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <button
        type="button"
        onClick={checkBackendAuthentication}
        disabled={loading}
      >
        {loading ? 'Checking...' : 'Test backend authentication'}
      </button>

      {message && <p role="status">{message}</p>}
    </section>
  )
}