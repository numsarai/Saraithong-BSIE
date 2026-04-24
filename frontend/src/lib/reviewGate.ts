export const REVIEW_CONFIDENCE_THRESHOLD = 75

export type MappingShape = Record<string, string | null | undefined>

export interface ReviewGateState {
  confidencePercent: number
  hasCriticalMapping: boolean
  bankNeedsReview: boolean
  bankOverrideDetected: boolean
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
  mapping: MappingShape
  bankReviewed: boolean
  mappingReviewed: boolean
}): ReviewGateState {
  const { detectedBank, selectedBankKey, mapping, bankReviewed, mappingReviewed } = params

  const confidencePercent = Math.round(Number(detectedBank?.confidence || 0) * 100)
  const ambiguous = Boolean(detectedBank?.ambiguous)
  const lowConfidence = confidencePercent < REVIEW_CONFIDENCE_THRESHOLD
  const detectedKey = String(detectedBank?.key || detectedBank?.config_key || '').trim().toLowerCase()
  const selectedKey = String(selectedBankKey || '').trim().toLowerCase()
  const bankOverrideDetected = !!selectedKey && !!detectedKey && selectedKey !== detectedKey
  const criticalMappingReady = hasCriticalMapping(mapping)

  const blockingReasons: string[] = []
  if (ambiguous) blockingReasons.push('Bank detection is ambiguous and requires analyst confirmation.')
  if (lowConfidence) blockingReasons.push(`Bank confidence is below ${REVIEW_CONFIDENCE_THRESHOLD}% and requires analyst confirmation.`)
  if (bankOverrideDetected) blockingReasons.push(`Selected bank (${selectedKey.toUpperCase()}) differs from detected bank (${detectedKey.toUpperCase()}) and requires analyst confirmation.`)
  if (!criticalMappingReady) blockingReasons.push('Critical mapping is incomplete. Map Date, Description, and one amount path before continuing.')

  const bankNeedsReview = ambiguous || lowConfidence || bankOverrideDetected
  const mappingNeedsReview = !criticalMappingReady
  const isBlockedCase = bankNeedsReview || mappingNeedsReview
  const canProceedToConfig = !isBlockedCase || (bankReviewed && mappingReviewed)

  return {
    confidencePercent,
    hasCriticalMapping: criticalMappingReady,
    bankNeedsReview,
    bankOverrideDetected,
    mappingNeedsReview,
    isBlockedCase,
    canProceedToConfig,
    blockingReasons,
  }
}
