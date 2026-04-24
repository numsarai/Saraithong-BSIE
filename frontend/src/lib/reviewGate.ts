export const REVIEW_CONFIDENCE_THRESHOLD = 75

export type MappingShape = Record<string, string | null | undefined>

export interface ReviewGateState {
  confidencePercent: number
  hasCriticalMapping: boolean
  bankNeedsReview: boolean
  bankOverrideDetected: boolean
  accountNeedsReview: boolean
  accountMismatchDetected: boolean
  accountPresenceNeedsReview: boolean
  mappingNeedsReview: boolean
  isBlockedCase: boolean
  canProceedToConfig: boolean
  blockingReasons: string[]
}

export function hasCriticalMapping(mapping: MappingShape): boolean {
  const hasDate = !!mapping.date
  const hasDescription = !!mapping.description
  const hasAmountPath = !!mapping.amount || !!mapping.debit || !!mapping.credit
  return hasDate && hasDescription && hasAmountPath
}

export function evaluateReviewGate(params: {
  detectedBank: any
  selectedBankKey?: string
  selectedAccount?: string
  inferredAccount?: string
  accountPresence?: any
  mapping: MappingShape
  bankReviewed: boolean
  accountReviewed?: boolean
  mappingReviewed: boolean
}): ReviewGateState {
  const { detectedBank, selectedBankKey, selectedAccount, inferredAccount, accountPresence, mapping, bankReviewed, accountReviewed, mappingReviewed } = params

  const confidencePercent = Math.round(Number(detectedBank?.confidence || 0) * 100)
  const ambiguous = Boolean(detectedBank?.ambiguous)
  const lowConfidence = confidencePercent < REVIEW_CONFIDENCE_THRESHOLD
  const detectedKey = String(detectedBank?.key || detectedBank?.config_key || '').trim().toLowerCase()
  const selectedKey = String(selectedBankKey || '').trim().toLowerCase()
  const bankOverrideDetected = !!selectedKey && !!detectedKey && selectedKey !== detectedKey
  const selectedAccountKey = normalizeAccount(selectedAccount)
  const inferredAccountKey = normalizeAccount(inferredAccount)
  const accountMismatchDetected = !!selectedAccountKey && !!inferredAccountKey && selectedAccountKey !== inferredAccountKey
  const accountPresenceStatus = String(accountPresence?.match_status || '').trim().toLowerCase()
  const accountPresenceNeedsReview = !!selectedAccountKey && (
    accountPresenceStatus === 'not_found'
    || accountPresenceStatus === 'possible_leading_zero_loss'
  )
  const criticalMappingReady = hasCriticalMapping(mapping)

  const blockingReasons: string[] = []
  if (ambiguous) blockingReasons.push('Bank detection is ambiguous and requires analyst confirmation.')
  if (lowConfidence) blockingReasons.push(`Bank confidence is below ${REVIEW_CONFIDENCE_THRESHOLD}% and requires analyst confirmation.`)
  if (bankOverrideDetected) blockingReasons.push(`Selected bank (${selectedKey.toUpperCase()}) differs from detected bank (${detectedKey.toUpperCase()}) and requires analyst confirmation.`)
  if (accountMismatchDetected) blockingReasons.push(`Selected account (${selectedAccountKey}) differs from inferred account (${inferredAccountKey}) and requires analyst confirmation.`)
  if (accountPresenceNeedsReview && accountPresenceStatus === 'not_found') {
    blockingReasons.push(`Selected account (${selectedAccountKey}) was not found in workbook verification and requires analyst confirmation.`)
  }
  if (accountPresenceNeedsReview && accountPresenceStatus === 'possible_leading_zero_loss') {
    blockingReasons.push(`Selected account (${selectedAccountKey}) only has possible leading-zero-loss workbook matches and requires analyst confirmation.`)
  }
  if (!criticalMappingReady) blockingReasons.push('Critical mapping is incomplete. Map Date, Description, and one amount path before continuing.')

  const bankNeedsReview = ambiguous || lowConfidence || bankOverrideDetected
  const accountNeedsReview = accountMismatchDetected || accountPresenceNeedsReview
  const mappingNeedsReview = !criticalMappingReady
  const isBlockedCase = bankNeedsReview || accountNeedsReview || mappingNeedsReview
  const canProceedToConfig = !isBlockedCase || (
    (!bankNeedsReview || bankReviewed)
    && (!accountNeedsReview || Boolean(accountReviewed))
    && (!mappingNeedsReview || mappingReviewed)
  )

  return {
    confidencePercent,
    hasCriticalMapping: criticalMappingReady,
    bankNeedsReview,
    bankOverrideDetected,
    accountNeedsReview,
    accountMismatchDetected,
    accountPresenceNeedsReview,
    mappingNeedsReview,
    isBlockedCase,
    canProceedToConfig,
    blockingReasons,
  }
}

function normalizeAccount(value: unknown): string {
  const digits = String(value || '').replace(/\D/g, '')
  return digits.length === 10 || digits.length === 12 ? digits : ''
}
