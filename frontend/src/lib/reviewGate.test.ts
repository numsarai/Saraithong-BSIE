import { describe, expect, it } from 'vitest'
import { evaluateReviewGate, hasCriticalMapping, REVIEW_CONFIDENCE_THRESHOLD } from '@/lib/reviewGate'

describe('reviewGate', () => {
  it('blocks ambiguous bank detection until both reviews are complete', () => {
    const gate = evaluateReviewGate({
      detectedBank: { confidence: 0.92, ambiguous: true },
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: false,
      mappingReviewed: false,
    })

    expect(gate.isBlockedCase).toBe(true)
    expect(gate.bankNeedsReview).toBe(true)
    expect(gate.mappingNeedsReview).toBe(false)
    expect(gate.canProceedToConfig).toBe(false)
  })

  it('blocks low confidence cases below the threshold even when not ambiguous', () => {
    const gate = evaluateReviewGate({
      detectedBank: { confidence: (REVIEW_CONFIDENCE_THRESHOLD - 1) / 100, ambiguous: false },
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: false,
      mappingReviewed: true,
    })

    expect(gate.bankNeedsReview).toBe(true)
    expect(gate.isBlockedCase).toBe(true)
    expect(gate.canProceedToConfig).toBe(false)
  })

  it('requires date, description, and one amount path for critical mapping', () => {
    expect(hasCriticalMapping({ date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' })).toBe(true)
    expect(hasCriticalMapping({ date: 'วันที่', description: 'รายละเอียด', debit: 'ถอนเงิน' })).toBe(true)
    expect(hasCriticalMapping({ date: 'วันที่', description: 'รายละเอียด', credit: 'ฝากเงิน' })).toBe(true)
    expect(hasCriticalMapping({ description: 'รายละเอียด', amount: 'จำนวนเงิน' })).toBe(false)
    expect(hasCriticalMapping({ date: 'วันที่', amount: 'จำนวนเงิน' })).toBe(false)
    expect(hasCriticalMapping({ date: 'วันที่', description: 'รายละเอียด' })).toBe(false)
  })

  it('unblocks when both reviews are completed for a blocked case', () => {
    const gate = evaluateReviewGate({
      detectedBank: { confidence: 0.6, ambiguous: false },
      mapping: { date: 'วันที่', description: 'รายละเอียด', debit: 'ถอนเงิน' },
      bankReviewed: true,
      mappingReviewed: true,
    })

    expect(gate.isBlockedCase).toBe(true)
    expect(gate.canProceedToConfig).toBe(true)
  })

  it('auto-clears when confidence and critical mapping are already good', () => {
    const gate = evaluateReviewGate({
      detectedBank: { confidence: 0.91, ambiguous: false },
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: true,
      mappingReviewed: true,
    })

    expect(gate.isBlockedCase).toBe(false)
    expect(gate.canProceedToConfig).toBe(true)
    expect(gate.blockingReasons).toEqual([])
  })

  it('blocks when analyst-selected bank differs from the detected bank', () => {
    const gate = evaluateReviewGate({
      detectedBank: { key: 'scb', confidence: 0.95, ambiguous: false },
      selectedBankKey: 'ktb',
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: false,
      mappingReviewed: true,
    })

    expect(gate.bankOverrideDetected).toBe(true)
    expect(gate.bankNeedsReview).toBe(true)
    expect(gate.isBlockedCase).toBe(true)
    expect(gate.canProceedToConfig).toBe(false)
    expect(gate.blockingReasons[0]).toMatch(/differs from detected bank/i)
  })

  it('blocks when analyst-selected account differs from the inferred account', () => {
    const gate = evaluateReviewGate({
      detectedBank: { key: 'scb', confidence: 0.95, ambiguous: false },
      selectedBankKey: 'scb',
      selectedAccount: '222-222-2222',
      inferredAccount: '1111111111',
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: true,
      accountReviewed: false,
      mappingReviewed: true,
    })

    expect(gate.accountMismatchDetected).toBe(true)
    expect(gate.accountNeedsReview).toBe(true)
    expect(gate.isBlockedCase).toBe(true)
    expect(gate.canProceedToConfig).toBe(false)
    expect(gate.blockingReasons[0]).toMatch(/selected account/i)
  })

  it('blocks when workbook verification cannot find the selected account', () => {
    const gate = evaluateReviewGate({
      detectedBank: { key: 'scb', confidence: 0.95, ambiguous: false },
      selectedBankKey: 'scb',
      selectedAccount: '1234567890',
      inferredAccount: '1234567890',
      accountPresence: { match_status: 'not_found', found: false, possible_match: false },
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: true,
      accountReviewed: false,
      mappingReviewed: true,
    })

    expect(gate.accountMismatchDetected).toBe(false)
    expect(gate.accountPresenceNeedsReview).toBe(true)
    expect(gate.accountNeedsReview).toBe(true)
    expect(gate.canProceedToConfig).toBe(false)
    expect(gate.blockingReasons[0]).toMatch(/not found in workbook verification/i)
  })

  it('allows possible leading-zero-loss workbook matches only after account review', () => {
    const gate = evaluateReviewGate({
      detectedBank: { key: 'scb', confidence: 0.95, ambiguous: false },
      selectedBankKey: 'scb',
      selectedAccount: '0123456789',
      inferredAccount: '0123456789',
      accountPresence: { match_status: 'possible_leading_zero_loss', found: false, possible_match: true },
      mapping: { date: 'วันที่', description: 'รายละเอียด', amount: 'จำนวนเงิน' },
      bankReviewed: true,
      accountReviewed: true,
      mappingReviewed: true,
    })

    expect(gate.accountPresenceNeedsReview).toBe(true)
    expect(gate.accountNeedsReview).toBe(true)
    expect(gate.canProceedToConfig).toBe(true)
    expect(gate.blockingReasons[0]).toMatch(/leading-zero-loss/i)
  })
})
