import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearStoredAuthToken, redetectFile, setStoredAuthToken } from '@/api'

describe('api auth headers', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    clearStoredAuthToken()
  })

  it('sends the stored bearer token when re-detecting an uploaded file', async () => {
    setStoredAuthToken('TOKEN-1')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await redetectFile('FILE-1', 'statement.xlsx')

    expect(fetchMock).toHaveBeenCalledWith('/api/redetect', expect.objectContaining({
      method: 'POST',
      headers: expect.any(Headers),
      body: JSON.stringify({ file_id: 'FILE-1', file_name: 'statement.xlsx' }),
    }))
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get('Authorization')).toBe('Bearer TOKEN-1')
  })
})
