const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/$/, '')
const AUTH_TOKEN_STORAGE_KEY = 'bsie.auth_token'

export function getStoredAuthToken() {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || ''
}

export function setStoredAuthToken(token: string) {
  if (typeof window === 'undefined') return
  if (token) window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
  else window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
}

export function clearStoredAuthToken() {
  setStoredAuthToken('')
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = new Headers(init.headers)
  const token = getStoredAuthToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  const response = await globalThis.fetch(url, { ...init, headers })
  if (response.status === 401 && token) clearStoredAuthToken()
  return response
}

export async function getAuthStatus() {
  const r = await apiFetch('/api/auth/status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function login(username: string, password: string) {
  const r = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!r.ok) throw new Error(await r.text())
  const payload = await r.json()
  setStoredAuthToken(payload.token || '')
  return payload
}

export async function getCurrentUser() {
  const r = await apiFetch('/api/auth/me')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function uploadFile(file: File, uploaded_by?: string, force_redetect?: boolean) {
  const fd = new FormData()
  fd.append('file', file)
  if (uploaded_by) fd.append('uploaded_by', uploaded_by)
  if (force_redetect) fd.append('force_redetect', '1')
  const r = await apiFetch('/api/upload', { method: 'POST', body: fd })
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
    subject_account?: string
    subject_name?: string
    identity_guess?: unknown
    account_presence?: unknown
    sample_rows?: Record<string, unknown>[]
    promote_shared?: boolean
  },
) {
  const r = await apiFetch('/api/mapping/confirm', {
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
      subject_account: context?.subject_account,
      subject_name: context?.subject_name,
      identity_guess: context?.identity_guess,
      account_presence: context?.account_presence,
      sample_rows: context?.sample_rows,
      promote_shared: context?.promote_shared ?? false,
    }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function previewMapping(payload: {
  bank: string
  mapping: Record<string, string | null>
  columns: string[]
  sample_rows?: Record<string, unknown>[]
}) {
  const r = await apiFetch('/api/mapping/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function verifyAccountPresence(payload: {
  file_id: string
  subject_account: string
  sheet_name?: string
  header_row?: number
  max_matches?: number
}) {
  const r = await apiFetch('/api/mapping/account-presence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export function evidencePreviewUrl(fileId: string, pageNumber?: number | null) {
  const page = Number(pageNumber || 0)
  const suffix = Number.isFinite(page) && page > 0 ? `#page=${encodeURIComponent(String(page))}` : ''
  return `${API_BASE}/api/files/${encodeURIComponent(fileId)}/evidence-preview${suffix}`
}

export async function assistMapping(payload: {
  bank: string
  detected_bank?: unknown
  columns: string[]
  sample_rows?: Record<string, unknown>[]
  current_mapping: Record<string, string | null>
  subject_account?: string
  subject_name?: string
  identity_guess?: unknown
  account_presence?: unknown
  sheet_name?: string
  header_row?: number
  model?: string
}) {
  const r = await apiFetch('/api/mapping/assist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function assistVisionMapping(payload: {
  file_id: string
  bank: string
  detected_bank?: unknown
  columns: string[]
  sample_rows?: Record<string, unknown>[]
  current_mapping: Record<string, string | null>
  subject_account?: string
  subject_name?: string
  identity_guess?: unknown
  account_presence?: unknown
  sheet_name?: string
  header_row?: number
  model?: string
}) {
  const r = await apiFetch('/api/mapping/assist/vision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function listMappingVariants(params: {
  bank?: string
  trust_state?: string
  limit?: number
} = {}) {
  const search = new URLSearchParams()
  if (params.bank) search.set('bank', params.bank)
  if (params.trust_state) search.set('trust_state', params.trust_state)
  if (params.limit) search.set('limit', String(params.limit))
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/mapping/variants${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function promoteMappingVariant(
  variantId: string,
  payload: {
    trust_state: string
    reviewer: string
    note?: string
  },
) {
  const r = await apiFetch(`/api/mapping/variants/${encodeURIComponent(variantId)}/promote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function markMappingVariantRollbackReview(
  variantId: string,
  payload: {
    reviewer: string
    note: string
  },
) {
  const r = await apiFetch(`/api/mapping/variants/${encodeURIComponent(variantId)}/rollback-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
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
  const r = await apiFetch('/api/process', {
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
  const r = await apiFetch('/api/process-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getJobStatus(jobId: string) {
  const r = await apiFetch(`/api/job/${jobId}`)
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
  const r = await apiFetch(`/api/results/${account}?${params.toString()}`)
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

export async function getResultsTimeline(account: string, parserRunId?: string | null) {
  const params = new URLSearchParams()
  if (parserRunId) params.set('parser_run_id', parserRunId)
  const r = await apiFetch(`/api/results/${account}/timeline?${params.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getTimelineAggregate(params: Record<string, string | number | undefined>) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  }
  const r = await apiFetch(`/api/transactions/timeline-aggregate?${qs.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAlerts(params: Record<string, string | number | undefined> = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  }
  const r = await apiFetch(`/api/alerts?${qs.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAlertSummary() {
  const r = await apiFetch('/api/alerts/summary')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAlertConfig() {
  const r = await apiFetch('/api/alerts/config')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function updateAlertConfig(config: Record<string, any>) {
  const r = await apiFetch('/api/alerts/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewAlert(alertId: string, status: string, reviewer: string = 'analyst', note: string = '') {
  const r = await apiFetch(`/api/alerts/${alertId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, reviewer, note }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function generateAccountReport(account: string, parserRunId?: string, analyst = 'analyst') {
  const r = await apiFetch('/api/reports/account', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account, parser_run_id: parserRunId || '', analyst }),
  })
  if (!r.ok) throw new Error(await r.text())
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${account}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

export async function generateCaseReport(accounts: string[], analyst = 'analyst') {
  const r = await apiFetch('/api/reports/case', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accounts, analyst }),
  })
  if (!r.ok) throw new Error(await r.text())
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'case_report.pdf'
  a.click()
  URL.revokeObjectURL(url)
}

export async function getAccountInsights(account: string) {
  const r = await apiFetch(`/api/analytics/insights?account=${account}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getSnaMetrics() {
  const r = await apiFetch('/api/analytics/sna')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccountProfile(accountId: string) {
  const r = await apiFetch(`/api/accounts/${accountId}/profile`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAnnotations(nodeId?: string) {
  const qs = nodeId ? `?node_id=${nodeId}` : ''
  const r = await apiFetch(`/api/annotations${qs}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export type CaseTagItem = {
  id: string
  tag: string
  description?: string | null
  created_at?: string | null
  linked_object_count?: number
  linked_object_counts?: Record<string, number>
}

export type CaseTagLinkedObject = {
  link_id: string
  object_type: string
  object_id: string
  citation_id?: string
  created_at?: string | null
  found?: boolean
  label?: string
  summary?: string
  scope?: {
    parser_run_id?: string
    file_id?: string
    account?: string
  }
  meta?: Record<string, unknown>
}

export type CaseTagDetail = CaseTagItem & {
  links: CaseTagLinkedObject[]
  limit?: number
}

export async function listCaseTags(): Promise<{ items: CaseTagItem[] }> {
  const r = await apiFetch('/api/case-tags')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getCaseTagDetail(caseTagId: string): Promise<CaseTagDetail> {
  const r = await apiFetch(`/api/case-tags/${encodeURIComponent(caseTagId)}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createAnnotation(nodeId: string, content: string, tag = '', createdBy = 'analyst') {
  const r = await apiFetch('/api/annotations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId, content, tag, type: tag ? 'tag' : 'note', created_by: createdBy }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteAnnotation(annotationId: string) {
  const r = await apiFetch(`/api/annotations/${annotationId}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function listWorkspaces() {
  const r = await apiFetch('/api/workspaces')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function saveWorkspace(data: Record<string, any>) {
  const r = await apiFetch('/api/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function loadWorkspace(workspaceId: string) {
  const r = await apiFetch(`/api/workspaces/${workspaceId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteWorkspace(workspaceId: string) {
  const r = await apiFetch(`/api/workspaces/${workspaceId}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccountFlows(account: string) {
  const r = await apiFetch(`/api/fund-flow/${account}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getMatchedTransactions(accountA: string, accountB: string) {
  const r = await apiFetch(`/api/fund-flow/${accountA}/to/${accountB}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function traceFundPath(from: string, to: string, maxHops = 4) {
  const r = await apiFetch(`/api/fund-flow/trace?from_account=${from}&to_account=${to}&max_hops=${maxHops}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

// ── LLM ──────────────────────────────────────────────────────────────────

export async function getLlmStatus() {
  const r = await apiFetch('/api/llm/status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function llmChat(message: string, opts?: { account?: string; transactions?: any[]; model?: string }) {
  const r = await apiFetch('/api/llm/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, ...opts }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function askCopilot(payload: {
  question: string
  task_mode?: string
  scope: {
    parser_run_id?: string
    file_id?: string
    account?: string
    case_tag_id?: string
    case_tag?: string
  }
  operator?: string
  model?: string
  max_transactions?: number
}) {
  const r = await apiFetch('/api/llm/copilot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function previewClassification(payload: {
  transactions?: Record<string, unknown>[]
  scope?: {
    parser_run_id?: string
    file_id?: string
    account?: string
    case_tag_id?: string
    case_tag?: string
  }
  model?: string
  max_transactions?: number
}) {
  const r = await apiFetch('/api/llm/classification-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function benchmarkLlm(opts?: {
  roles?: string[]
  iterations?: number
  include_vision?: boolean
  model_overrides?: Record<string, string>
}) {
  const r = await apiFetch('/api/llm/benchmark', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts || {}),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function llmSummarize(transactions: any[], account?: string, model?: string) {
  const r = await apiFetch('/api/llm/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transactions, account, model }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDashboard() {
  const r = await apiFetch('/api/dashboard')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function annotateTransaction(transactionId: string, note: string, reviewer = 'analyst') {
  const r = await apiFetch(`/api/transactions/${transactionId}/annotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note, reviewer }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAuditTrail(objectType: string, objectId: string) {
  const r = await apiFetch(`/api/audit-trail/${objectType}/${objectId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getFiles() {
  const r = await apiFetch('/api/files')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDbStatus() {
  const r = await apiFetch('/api/admin/db-status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDataHygiene() {
  const r = await apiFetch('/api/admin/data-hygiene')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackups() {
  const r = await apiFetch('/api/admin/backups')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackupSettings() {
  const r = await apiFetch('/api/admin/backup-settings')
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
  const r = await apiFetch('/api/admin/backup-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDatabaseBackupPreview(backupName: string) {
  const r = await apiFetch(`/api/admin/backups/${encodeURIComponent(backupName)}/preview`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createDatabaseBackup(payload: { operator?: string; note?: string; backup_format?: string }) {
  const r = await apiFetch('/api/admin/backup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function resetDatabase(payload: { confirm_text: string; operator?: string; note?: string; create_pre_reset_backup?: boolean }) {
  const r = await apiFetch('/api/admin/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function restoreDatabase(payload: { backup_filename: string; confirm_text: string; operator?: string; note?: string; create_pre_restore_backup?: boolean }) {
  const r = await apiFetch('/api/admin/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getFileDetail(fileId: string) {
  const r = await apiFetch(`/api/files/${fileId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getParserRuns(fileId?: string) {
  const suffix = fileId ? `?file_id=${encodeURIComponent(fileId)}` : ''
  const r = await apiFetch(`/api/parser-runs${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getParserRunDetail(parserRunId: string) {
  const r = await apiFetch(`/api/parser-runs/${parserRunId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reprocessParserRun(parserRunId: string, payload: { reviewer: string; reviewer_note?: string; decision_value: string }) {
  const r = await apiFetch(`/api/parser-runs/${parserRunId}/reprocess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccounts(q = '') {
  const suffix = q ? `?q=${encodeURIComponent(q)}` : ''
  const r = await apiFetch(`/api/accounts${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function lookupRememberedAccountName(params: { account: string; bank_key?: string }) {
  const search = new URLSearchParams()
  search.set('account', params.account)
  if (params.bank_key) search.set('bank_key', params.bank_key)
  const r = await apiFetch(`/api/accounts/remembered-name?${search.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAccountDetail(accountId: string) {
  const r = await apiFetch(`/api/accounts/${accountId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function searchTransactionRecords(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const r = await apiFetch(`/api/transactions/search?${search.toString()}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getTransactionDetail(transactionId: string) {
  const r = await apiFetch(`/api/transactions/${transactionId}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getDuplicates() {
  const r = await apiFetch('/api/duplicates')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewDuplicate(groupId: string, payload: { decision_value: string; reviewer: string; reviewer_note?: string }) {
  const r = await apiFetch(`/api/duplicates/${groupId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getMatches(status = '') {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : ''
  const r = await apiFetch(`/api/matches${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewMatch(matchId: string, payload: { decision_value: string; reviewer: string; reviewer_note?: string }) {
  const r = await apiFetch(`/api/matches/${matchId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewTransaction(transactionId: string, payload: { reviewer: string; reason?: string; changes: Record<string, any> }) {
  const r = await apiFetch(`/api/transactions/${transactionId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function reviewAccount(accountId: string, payload: { reviewer: string; reason?: string; changes: Record<string, any> }) {
  const r = await apiFetch(`/api/accounts/${accountId}/review`, {
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
  const r = await apiFetch(`/api/audit-logs${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getLearningFeedbackLogs(params: Record<string, string | number | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/learning-feedback${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getExportJobs() {
  const r = await apiFetch('/api/export-jobs')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphAnalysis(params: Record<string, string | number | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph-analysis${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNodes(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph/nodes${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphEdges(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph/edges${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphDerivedEdges(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph/derived-edges${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphFindings(params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph/findings${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNeighborhood(nodeId: string, params: Record<string, string | number | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') search.set(key, `${value}`)
  })
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const r = await apiFetch(`/api/graph/neighborhood/${encodeURIComponent(nodeId)}${suffix}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getGraphNeo4jStatus() {
  const r = await apiFetch('/api/graph/neo4j-status')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function syncGraphToNeo4j(payload: { include_findings?: boolean; limit?: number; filters?: Record<string, any> }) {
  const r = await apiFetch('/api/graph/neo4j-sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createExportJob(payload: { export_type: string; filters?: Record<string, any>; created_by?: string }) {
  const r = await apiFetch('/api/exports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBulkAnalytics(runId: string) {
  const r = await apiFetch(`/api/bulk/${runId}/analytics`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBanks() {
  const r = await apiFetch('/api/banks')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBankLogoCatalog() {
  const r = await apiFetch('/api/bank-logo-catalog')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getBank(key: string) {
  const r = await apiFetch(`/api/banks/${key}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createBank(payload: Record<string, any>) {
  const r = await apiFetch('/api/banks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteBank(key: string) {
  const r = await apiFetch(`/api/banks/${key}`, { method: 'DELETE' })
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
  const r = await apiFetch('/api/banks/learn', {
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
  const r = await apiFetch('/api/override', {
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
  const r = await apiFetch('/api/overrides')
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteOverride(transactionId: string, accountNumber: string, operator?: string) {
  const params = new URLSearchParams()
  if (accountNumber) params.set('account_number', accountNumber)
  if (operator) params.set('operator', operator)
  const r = await apiFetch(`/api/override/${encodeURIComponent(transactionId)}?${params.toString()}`, {
    method: 'DELETE',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
