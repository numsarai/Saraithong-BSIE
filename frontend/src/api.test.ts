import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearStoredAuthToken, generateAccountReport, redetectFile, setStoredAuthToken } from '@/api'

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

  it('requests local LLM analysis when generating the investigation report PDF', async () => {
    const originalCreateObjectURL = URL.createObjectURL
    const originalRevokeObjectURL = URL.revokeObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:report')
    URL.revokeObjectURL = vi.fn()
    const click = vi.fn()
    const originalCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName)
      if (tagName.toLowerCase() === 'a') {
        Object.defineProperty(element, 'click', { value: click })
      }
      return element
    })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(new Blob(['PDF']), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      }),
    )

    try {
      await generateAccountReport('1883167399', 'RUN-1', 'Case Reviewer')
    } finally {
      URL.createObjectURL = originalCreateObjectURL
      URL.revokeObjectURL = originalRevokeObjectURL
    }

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(fetchMock.mock.calls[0][0]).toBe('/api/reports/account')
    expect(JSON.parse(String(init.body))).toEqual({
      account: '1883167399',
      parser_run_id: 'RUN-1',
      analyst: 'Case Reviewer',
      include_llm_analysis: true,
    })
    expect(click).toHaveBeenCalled()
  })
})
