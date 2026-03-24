import { create } from 'zustand'

export type Tab = 'transactions' | 'entities' | 'links'

export interface AppState {
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
  setBankKey: (key: string) => void
  setAccount: (account: string) => void
  setName: (name: string) => void
  setJobId: (id: string) => void
  setResults: (results: any) => void
  setCurrentTab: (tab: Tab) => void
  setTxnPage: (page: number) => void
  setTxnTotal: (total: number) => void
  setBanks: (banks: any[]) => void
  reset: () => void
}

const initialState = {
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
  setUploadResult: (data, filename) => set({
    tempFilePath: data.temp_file_path,
    fileName: filename,
    detectedBank: data.detected_bank,
    suggestedMapping: data.suggested_mapping || {},
    confirmedMapping: data.suggested_mapping || {},
    allColumns: data.all_columns || [],
    confidenceScores: data.confidence_scores || {},
    sampleRows: data.sample_rows || [],
    bankKey: data.detected_bank?.key || '',
  }),
  setConfirmedMapping: (mapping) => set({ confirmedMapping: mapping }),
  setBankKey: (bankKey) => set({ bankKey }),
  setAccount: (account) => set({ account }),
  setName: (name) => set({ name }),
  setJobId: (jobId) => set({ jobId }),
  setResults: (results) => set({ results }),
  setCurrentTab: (currentTab) => set({ currentTab }),
  setTxnPage: (txnPage) => set({ txnPage }),
  setTxnTotal: (txnTotal) => set({ txnTotal }),
  setBanks: (banks) => set({ banks }),
  reset: () => set(initialState),
}))
