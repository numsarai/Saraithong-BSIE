import { create } from 'zustand'
import { evaluateReviewGate } from '@/lib/reviewGate'

export type Tab = 'transactions' | 'entities' | 'links'
export type Page = 'main' | 'bank-manager' | 'bulk-intake' | 'investigation'
export const DEFAULT_OPERATOR_NAME = 'analyst'

const OPERATOR_STORAGE_KEY = 'bsie.operator_name'

function getBrowserStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  const maybeStorage = window.localStorage
  if (!maybeStorage || typeof maybeStorage.getItem !== 'function' || typeof maybeStorage.setItem !== 'function') {
    return null
  }
  return maybeStorage
}

function readStoredOperatorName() {
  const storage = getBrowserStorage()
  if (!storage) return DEFAULT_OPERATOR_NAME
  const stored = storage.getItem(OPERATOR_STORAGE_KEY)
  return stored?.trim() || DEFAULT_OPERATOR_NAME
}

function persistOperatorName(value: string) {
  const storage = getBrowserStorage()
  if (!storage) return
  const nextValue = value.trim()
  if (nextValue) {
    storage.setItem(OPERATOR_STORAGE_KEY, nextValue)
    return
  }
  storage.removeItem(OPERATOR_STORAGE_KEY)
}

export function normalizeOperatorName(value: string | null | undefined) {
  return String(value || '').trim() || DEFAULT_OPERATOR_NAME
}

export interface AppState {
  page: Page
  step: number
  operatorName: string
  jobId: string | null
  fileId: string | null
  parserRunId: string | null
  tempFilePath: string | null
  fileName: string | null
  detectedBank: any
  suggestedMapping: Record<string, string | null>
  confirmedMapping: Record<string, string | null>
  allColumns: string[]
  confidenceScores: Record<string, number>
  sampleRows: any[]
  headerRow: number
  sheetName: string
  identityGuess: any | null
  memoryMatch: any | null
  bankMemoryMatch: any | null
  bankReviewed: boolean
  mappingReviewed: boolean
  isBlockedCase: boolean
  canProceedToConfig: boolean
  bankKey: string
  account: string
  name: string
  results: any | null
  currentTab: Tab
  txnPage: number
  txnTotal: number
  banks: any[]
  bulkSummary: any | null
  setStep: (step: number) => void
  setOperatorName: (operatorName: string) => void
  setUploadResult: (data: any, filename: string) => void
  setConfirmedMapping: (mapping: Record<string, string | null>) => void
  setBankReviewed: (reviewed: boolean) => void
  setMappingReviewed: (reviewed: boolean) => void
  setBankKey: (key: string) => void
  setAccount: (account: string) => void
  setName: (name: string) => void
  setJobId: (id: string) => void
  setParserRunId: (id: string | null) => void
  setResults: (results: any) => void
  setCurrentTab: (tab: Tab) => void
  setTxnPage: (page: number) => void
  setTxnTotal: (total: number) => void
  setBanks: (banks: any[]) => void
  setBulkSummary: (summary: any | null) => void
  setPage: (page: Page) => void
  reset: () => void
}

const workflowInitialState = {
  page: 'main' as Page,
  step: 1,
  jobId: null as string | null,
  fileId: null as string | null,
  parserRunId: null as string | null,
  tempFilePath: null as string | null,
  fileName: null as string | null,
  detectedBank: null as any,
  suggestedMapping: {} as Record<string, string | null>,
  confirmedMapping: {} as Record<string, string | null>,
  allColumns: [] as string[],
  confidenceScores: {} as Record<string, number>,
  sampleRows: [] as any[],
  headerRow: 0,
  sheetName: '',
  identityGuess: null as any | null,
  memoryMatch: null as any | null,
  bankMemoryMatch: null as any | null,
  bankReviewed: false,
  mappingReviewed: false,
  isBlockedCase: false,
  canProceedToConfig: false,
  bankKey: '',
  account: '',
  name: '',
  results: null as any | null,
  currentTab: 'transactions' as Tab,
  txnPage: 1,
  txnTotal: 0,
  banks: [] as any[],
  bulkSummary: null as any | null,
}

export const useStore = create<AppState>((set) => ({
  ...workflowInitialState,
  operatorName: readStoredOperatorName(),
  setStep: (step) => set({ step }),
  setOperatorName: (operatorName) => set(() => {
    const nextOperatorName = String(operatorName || '').slice(0, 80)
    persistOperatorName(nextOperatorName)
    return { operatorName: nextOperatorName }
  }),
  setUploadResult: (data, filename) => set(() => {
    const detectedBank = data.detected_bank
    const confirmedMapping = data.suggested_mapping || {}
    const bankReviewed = !evaluateReviewGate({
      detectedBank,
      mapping: confirmedMapping,
      bankReviewed: false,
      mappingReviewed: false,
    }).bankNeedsReview
    const mappingReviewed = !evaluateReviewGate({
      detectedBank,
      mapping: confirmedMapping,
      bankReviewed,
      mappingReviewed: false,
    }).mappingNeedsReview
    const gate = evaluateReviewGate({
      detectedBank,
      mapping: confirmedMapping,
      bankReviewed,
      mappingReviewed,
    })

    return {
      tempFilePath: data.temp_file_path,
      fileId: data.file_id || null,
      fileName: filename,
      detectedBank,
      suggestedMapping: confirmedMapping,
      confirmedMapping,
      allColumns: data.all_columns || [],
      confidenceScores: data.confidence_scores || {},
      sampleRows: data.sample_rows || [],
      headerRow: data.header_row || 0,
      sheetName: data.sheet_name || '',
      identityGuess: data.identity_guess || null,
      memoryMatch: data.memory_match || null,
      bankMemoryMatch: data.bank_memory_match || null,
      bankReviewed,
      mappingReviewed,
      isBlockedCase: gate.isBlockedCase,
      canProceedToConfig: gate.canProceedToConfig,
      bankKey: detectedBank?.key || '',
      account: data.account_guess || '',
      name: data.name_guess || '',
    }
  }),
  setConfirmedMapping: (mapping) => set((state) => {
    const gateBeforeReset = evaluateReviewGate({
      detectedBank: state.detectedBank,
      mapping,
      bankReviewed: state.bankReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    const mappingReviewed = gateBeforeReset.mappingNeedsReview ? false : state.mappingReviewed
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      mapping,
      bankReviewed: state.bankReviewed,
      mappingReviewed,
    })
    return {
      confirmedMapping: mapping,
      mappingReviewed,
      isBlockedCase: gate.isBlockedCase,
      canProceedToConfig: gate.canProceedToConfig,
    }
  }),
  setBankReviewed: (bankReviewed) => set((state) => {
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      mapping: state.confirmedMapping,
      bankReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { bankReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setMappingReviewed: (mappingReviewed) => set((state) => {
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      mappingReviewed,
    })
    return { mappingReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setBankKey: (bankKey) => set((state) => {
    const bankReviewed = false
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      mapping: state.confirmedMapping,
      bankReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { bankKey, bankReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setAccount: (account) => set({ account }),
  setName: (name) => set({ name }),
  setJobId: (jobId) => set({ jobId }),
  setParserRunId: (parserRunId) => set({ parserRunId }),
  setResults: (results) => set({ results }),
  setCurrentTab: (currentTab) => set({ currentTab }),
  setTxnPage: (txnPage) => set({ txnPage }),
  setTxnTotal: (txnTotal) => set({ txnTotal }),
  setBanks: (banks) => set({ banks }),
  setBulkSummary: (bulkSummary) => set({ bulkSummary }),
  setPage: (page) => set({ page }),
  reset: () => set((state) => ({
    ...workflowInitialState,
    operatorName: state.operatorName,
  })),
}))
