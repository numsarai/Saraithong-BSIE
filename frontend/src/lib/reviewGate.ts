export const REVIEW_CONFIDENCE_THRESHOLD = 75

export type MappingShape = Record<string, string | null | undefined>

export interface ReviewGateState {
  confidencePercent: number
  hasCriticalMapping: boolean
  bankNeedsReview: boolean
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
  mapping: MappingShape
  bankReviewed: boolean
  mappingReviewed: boolean
}): ReviewGateState {
  const { detectedBank, mapping, bankReviewed, mappingReviewed } = params

  const confidencePercent = Math.round(Number(detectedBank?.confidence || 0) * 100)
  const ambiguous = Boolean(detectedBank?.ambiguous)
  const lowConfidence = confidencePercent < REVIEW_CONFIDENCE_THRESHOLD
  const criticalMappingReady = hasCriticalMapping(mapping)

  const blockingReasons: string[] = []
  if (ambiguous) blockingReasons.push('Bank detection is ambiguous and requires analyst confirmation.')
  if (lowConfidence) blockingReasons.push(`Bank confidence is below ${REVIEW_CONFIDENCE_THRESHOLD}% and requires analyst confirmation.`)
  if (!criticalMappingReady) blockingReasons.push('Critical mapping is incomplete. Map Date, Description, and one amount path before continuing.')

  const bankNeedsReview = ambiguous || lowConfidence
  const mappingNeedsReview = !criticalMappingReady
  const isBlockedCase = bankNeedsReview || mappingNeedsReview
  const canProceedToConfig = !isBlockedCase || (bankReviewed && mappingReviewed)

  return {
    confidencePercent,
    hasCriticalMapping: criticalMappingReady,
    bankNeedsReview,
    mappingNeedsReview,
    isBlockedCase,
    canProceedToConfig,
    blockingReasons,
  }
}
