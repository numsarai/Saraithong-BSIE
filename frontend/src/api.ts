export async function uploadFile(file: File, uploaded_by?: string) {
  const fd = new FormData()
  fd.append('file', file)
  if (uploaded_by) fd.append('uploaded_by', uploaded_by)
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
  context?: {
    reviewer?: string
    detected_bank?: unknown
    suggested_mapping?: Record<string, string | null>
  },
) {
  const r = await fetch('/api/mapping/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank,
      mapping,
      columns,
      header_row,
      sheet_name,
      reviewer: context?.reviewer,
      detected_bank: context?.detected_bank,
      suggested_mapping: context?.suggested_mapping,
    }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function startProcess(payload: {
  temp_file_path?: string
  file_id?: string | null
  bank_key: string
  account: string
  name: string
  confirmed_mapping: Record<string, string | null>
  operator?: string
  header_row?: number
  sheet_name?: string
}) {
  const r = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function processFolder(payload: {
  folder_path: string
  recursive: boolean
  operator?: string
}) {
  const r = await fetch('/api/process-folder', {
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

export async function getResults(account: string, page = 1, pageSize = 100, parserRunId?: string | null) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (parserRunId) {
    params.set('parser_run_id', parserRunId)
  }
  const r = await fetch(`/api/results/${account}?${params.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  const payload = await r.json()
  if (!payload.rows && Array.isArray(payload.items)) {
    payload.rows = payload.items
  }
  if (!payload.items && Array.isArray(payload.rows)) {
    payload.items = payload.rows
  }
  return payload
}

export async function getFiles() {
  const r = await fetch('/api/files')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDbStatus() {
  const r = await fetch('/api/admin/db-status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackups() {
  const r = await fetch('/api/admin/backups')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackupSettings() {
  const r = await fetch('/api/admin/backup-settings')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function updateDatabaseBackupSettings(payload: {
  enabled: boolean
  interval_hours: number
  backup_format: string
  retention_enabled: boolean
  retain_count: number
  updated_by?: string
}) {
  const r = await fetch('/api/admin/backup-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackupPreview(backupName: string) {
  const r = await fetch(`/api/admin/backups/${encodeURIComponent(backupName)}/preview`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createDatabaseBackup(payload: { operator?: string; note?: string; backup_format?: string }) {
  const r = await fetch('/api/admin/backup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function resetDatabase(payload: { confirm_text: string; operator?: string; note?: string; create_pre_reset_backup?: boolean }) {
  const r = await fetch('/api/admin/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function restoreDatabase(payload: { backup_filename: string; confirm_text: string; operator?: string; note?: string; create_pre_restore_backup?: boolean }) {
  const r = await fetch('/api/admin/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getFileDetail(fileId: string) {
  const r = await fetch(`/api/files/${fileId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getParserRuns(fileId?: string) {
  const suffix = fileId ? `?file_id=${encodeURIComponent(fileId)}` : ''
  const r = await fetch(`/api/parser-runs${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getParserRunDetail(parserRunId: string) {
  const r = await fetch(`/api/parser-runs/${parserRunId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reprocessParserRun(parserRunId: string, payload: { reviewer: string; reviewer_note?: string; decision_value: string }) {
  const r = await fetch(`/api/parser-runs/${parserRunId}/reprocess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccounts(q = '') {
  const suffix = q ? `?q=${encodeURIComponent(q)}` : ''
  const r = await fetch(`/api/accounts${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function lookupRememberedAccountName(params: { account: string; bank_key?: string }) {
  const search = new URLSearchParams()
  search.set('account', params.account)
  if (params.bank_key) search.set('bank_key', params.bank_key)
  const r = await fetch(`/api/accounts/remembered-name?${search.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccountDetail(accountId: string) {
  const r = await fetch(`/api/accounts/${accountId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function searchTransactionRecords(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const r = await fetch(`/api/transactions/search?${search.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getTransactionDetail(transactionId: string) {
  const r = await fetch(`/api/transactions/${transactionId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDuplicates() {
  const r = await fetch('/api/duplicates')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewDuplicate(groupId: string, payload: { decision_value: string; reviewer: string; reviewer_note?: string }) {
  const r = await fetch(`/api/duplicates/${groupId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getMatches(status = '') {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : ''
  const r = await fetch(`/api/matches${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewMatch(matchId: string, payload: { decision_value: string; reviewer: string; reviewer_note?: string }) {
  const r = await fetch(`/api/matches/${matchId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewTransaction(transactionId: string, payload: { reviewer: string; reason?: string; changes: Record<string, any> }) {
  const r = await fetch(`/api/transactions/${transactionId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewAccount(accountId: string, payload: { reviewer: string; reason?: string; changes: Record<string, any> }) {
  const r = await fetch(`/api/accounts/${accountId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAuditLogs(params: Record<string, string | number | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/audit-logs${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getLearningFeedbackLogs(params: Record<string, string | number | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/learning-feedback${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getExportJobs() {
  const r = await fetch('/api/export-jobs')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphAnalysis(params: Record<string, string | number | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph-analysis${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNodes(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph/nodes${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphEdges(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph/edges${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphDerivedEdges(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph/derived-edges${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphFindings(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph/findings${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNeighborhood(nodeId: string, params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await fetch(`/api/graph/neighborhood/${encodeURIComponent(nodeId)}${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNeo4jStatus() {
  const r = await fetch('/api/graph/neo4j-status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function syncGraphToNeo4j(payload: { include_findings?: boolean; limit?: number; filters?: Record<string, any> }) {
  const r = await fetch('/api/graph/neo4j-sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createExportJob(payload: { export_type: string; filters?: Record<string, any>; created_by?: string }) {
  const r = await fetch('/api/exports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBulkAnalytics(runId: string) {
  const r = await fetch(`/api/bulk/${runId}/analytics`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBanks() {
  const r = await fetch('/api/banks')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBankLogoCatalog() {
  const r = await fetch('/api/bank-logo-catalog')
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
  account_number: string
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
      account_number: payload.account_number,
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

export async function getOverrides() {
  const r = await fetch('/api/overrides')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteOverride(transactionId: string, accountNumber: string, operator?: string) {
  const params = new URLSearchParams()
  if (accountNumber) params.set('account_number', accountNumber)
  if (operator) params.set('operator', operator)
  const r = await fetch(`/api/override/${encodeURIComponent(transactionId)}?${params.toString()}`, {
    method: 'DELETE',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
