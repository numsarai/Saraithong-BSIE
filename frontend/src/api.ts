export async function uploadFile(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch('/api/upload', { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function confirmMapping(
  bank: string,
  mapping: Record<string, string | null>,
  columns: string[],
  header_row?: number,
  sheet_name?: string,
) {
  const r = await fetch('/api/mapping/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bank, mapping, columns, header_row, sheet_name }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function startProcess(payload: {
  temp_file_path: string
  bank_key: string
  account: string
  name: string
  confirmed_mapping: Record<string, string | null>
}) {
  const r = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getJobStatus(jobId: string) {
  const r = await fetch(`/api/job/${jobId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getResults(account: string, page = 1, pageSize = 100) {
  const r = await fetch(`/api/results/${account}?page=${page}&page_size=${pageSize}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBanks() {
  const r = await fetch('/api/banks')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBank(key: string) {
  const r = await fetch(`/api/banks/${key}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createBank(payload: Record<string, any>) {
  const r = await fetch('/api/banks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteBank(key: string) {
  const r = await fetch(`/api/banks/${key}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function learnBank(payload: {
  key: string
  bank_name: string
  format_type: string
  amount_mode: string
  confirmed_mapping: Record<string, string | null>
  all_columns: string[]
}) {
  const r = await fetch('/api/banks/learn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function saveOverride(payload: {
  transaction_id: string
  from_account: string
  to_account: string
  reason: string
  override_by: string
}) {
  const r = await fetch('/api/override', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      transaction_id: payload.transaction_id,
      override_from_account: payload.from_account,
      override_to_account: payload.to_account,
      override_reason: payload.reason,
      override_by: payload.override_by,
    }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
