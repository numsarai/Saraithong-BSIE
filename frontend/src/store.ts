import { create } from 'zustand'
import { evaluateReviewGate } from '@/lib/reviewGate'

export type Tab = 'transactions' | 'entities' | 'links'
export type Page = 'main' | 'bank-manager'

export interface AppState {
  page: Page
  step: number
  jobId: string | null
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
  setStep: (step: number) => void
  setUploadResult: (data: any, filename: string) => void
  setConfirmedMapping: (mapping: Record<string, string | null>) => void
  setBankReviewed: (reviewed: boolean) => void
  setMappingReviewed: (reviewed: boolean) => void
  setBankKey: (key: string) => void
  setAccount: (account: string) => void
  setName: (name: string) => void
  setJobId: (id: string) => void
  setResults: (results: any) => void
  setCurrentTab: (tab: Tab) => void
  setTxnPage: (page: number) => void
  setTxnTotal: (total: number) => void
  setBanks: (banks: any[]) => void
  setPage: (page: Page) => void
  reset: () => void
}

const initialState = {
  page: 'main' as Page,
  step: 1,
  jobId: null,
  tempFilePath: null,
  fileName: null,
  detectedBank: null,
  suggestedMapping: {},
  confirmedMapping: {},
  allColumns: [],
  confidenceScores: {},
  sampleRows: [],
  headerRow: 0,
  sheetName: '',
  memoryMatch: null,
  bankMemoryMatch: null,
  bankReviewed: false,
  mappingReviewed: false,
  isBlockedCase: false,
  canProceedToConfig: false,
  bankKey: '',
  account: '',
  name: '',
  results: null,
  currentTab: 'transactions' as Tab,
  txnPage: 1,
  txnTotal: 0,
  banks: [],
}

export const useStore = create<AppState>((set) => ({
  ...initialState,
  setStep: (step) => set({ step }),
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
      fileName: filename,
      detectedBank,
      suggestedMapping: confirmedMapping,
      confirmedMapping,
      allColumns: data.all_columns || [],
      confidenceScores: data.confidence_scores || {},
      sampleRows: data.sample_rows || [],
      headerRow: data.header_row || 0,
      sheetName: data.sheet_name || '',
      memoryMatch: data.memory_match || null,
      bankMemoryMatch: data.bank_memory_match || null,
      bankReviewed,
      mappingReviewed,
      isBlockedCase: gate.isBlockedCase,
      canProceedToConfig: gate.canProceedToConfig,
      bankKey: detectedBank?.key || '',
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
  setResults: (results) => set({ results }),
  setCurrentTab: (currentTab) => set({ currentTab }),
  setTxnPage: (txnPage) => set({ txnPage }),
  setTxnTotal: (txnTotal) => set({ txnTotal }),
  setBanks: (banks) => set({ banks }),
  setPage: (page) => set({ page }),
  reset: () => set(initialState),
}))
