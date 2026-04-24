import { create } from 'zustand'
import { evaluateReviewGate } from '@/lib/reviewGate'
import i18n from '@/i18n'

export type Tab = 'transactions' | 'entities' | 'links'
export type Page = 'main' | 'dashboard' | 'bank-manager' | 'bulk-intake' | 'investigation'
export type Locale = 'th' | 'en'
export type Theme = 'light' | 'dark'
export const DEFAULT_OPERATOR_NAME = 'analyst'

const OPERATOR_STORAGE_KEY = 'bsie.operator_name'
const LOCALE_STORAGE_KEY = 'bsie.language'
const THEME_STORAGE_KEY = 'bsie.theme'

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

function readStoredTheme(): Theme {
  const storage = getBrowserStorage()
  if (!storage) return 'dark'
  const stored = storage.getItem(THEME_STORAGE_KEY)
  return stored === 'light' ? 'light' : 'dark'
}

function persistTheme(theme: Theme) {
  const storage = getBrowserStorage()
  if (!storage) return
  storage.setItem(THEME_STORAGE_KEY, theme)
  // Apply class to documentElement
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }
}

function readStoredLocale(): Locale {
  const storage = getBrowserStorage()
  if (!storage) return 'th'
  const stored = storage.getItem(LOCALE_STORAGE_KEY)
  return stored === 'en' ? 'en' : 'th'
}

function persistLocale(locale: Locale) {
  const storage = getBrowserStorage()
  if (!storage) return
  storage.setItem(LOCALE_STORAGE_KEY, locale)
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
  locale: Locale
  theme: Theme
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
  templateVariantMatch: any | null
  suggestionSource: string
  bankReviewed: boolean
  accountReviewed: boolean
  accountPresence: any | null
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
  setLocale: (locale: Locale) => void
  setTheme: (theme: Theme) => void
  setOperatorName: (operatorName: string) => void
  setUploadResult: (data: any, filename: string) => void
  setConfirmedMapping: (mapping: Record<string, string | null>) => void
  setBankReviewed: (reviewed: boolean) => void
  setAccountReviewed: (reviewed: boolean) => void
  setAccountPresence: (presence: any | null) => void
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
  templateVariantMatch: null as any | null,
  suggestionSource: 'auto',
  bankReviewed: false,
  accountReviewed: false,
  accountPresence: null as any | null,
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
  locale: readStoredLocale(),
  theme: readStoredTheme(),
  operatorName: readStoredOperatorName(),
  setStep: (step) => set({ step }),
  setLocale: (locale) => set(() => {
    persistLocale(locale)
    i18n.changeLanguage(locale)
    return { locale }
  }),
  setTheme: (theme) => set(() => {
    persistTheme(theme)
    return { theme }
  }),
  setOperatorName: (operatorName) => set(() => {
    const nextOperatorName = String(operatorName || '').slice(0, 80)
    persistOperatorName(nextOperatorName)
    return { operatorName: nextOperatorName }
  }),
  setUploadResult: (data, filename) => set(() => {
    const detectedBank = data.detected_bank
    const confirmedMapping = data.suggested_mapping || {}
    const selectedBankKey = detectedBank?.key || detectedBank?.config_key || ''
    const selectedAccount = data.account_guess || ''
    const inferredAccount = data.identity_guess?.account || data.account_guess || ''
    const bankReviewed = !evaluateReviewGate({
      detectedBank,
      selectedBankKey,
      selectedAccount,
      inferredAccount,
      accountPresence: null,
      mapping: confirmedMapping,
      bankReviewed: false,
      accountReviewed: false,
      mappingReviewed: false,
    }).bankNeedsReview
    const accountReviewed = !evaluateReviewGate({
      detectedBank,
      selectedBankKey,
      selectedAccount,
      inferredAccount,
      accountPresence: null,
      mapping: confirmedMapping,
      bankReviewed,
      accountReviewed: false,
      mappingReviewed: false,
    }).accountNeedsReview
    const mappingReviewed = !evaluateReviewGate({
      detectedBank,
      selectedBankKey,
      selectedAccount,
      inferredAccount,
      accountPresence: null,
      mapping: confirmedMapping,
      bankReviewed,
      accountReviewed,
      mappingReviewed: false,
    }).mappingNeedsReview
    const gate = evaluateReviewGate({
      detectedBank,
      selectedBankKey,
      selectedAccount,
      inferredAccount,
      accountPresence: null,
      mapping: confirmedMapping,
      bankReviewed,
      accountReviewed,
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
      templateVariantMatch: data.template_variant_match || null,
      suggestionSource: data.suggestion_source || 'auto',
      bankReviewed,
      accountReviewed,
      mappingReviewed,
      isBlockedCase: gate.isBlockedCase,
      canProceedToConfig: gate.canProceedToConfig,
      bankKey: selectedBankKey,
      account: selectedAccount,
      accountPresence: null,
      name: data.name_guess || '',
    }
  }),
  setConfirmedMapping: (mapping) => set((state) => {
    const gateBeforeReset = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping,
      bankReviewed: state.bankReviewed,
      accountReviewed: state.accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    const mappingReviewed = gateBeforeReset.mappingNeedsReview ? false : state.mappingReviewed
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping,
      bankReviewed: state.bankReviewed,
      accountReviewed: state.accountReviewed,
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
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed,
      accountReviewed: state.accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { bankReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setAccountReviewed: (accountReviewed) => set((state) => {
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { accountReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setAccountPresence: (accountPresence) => set((state) => {
    const gateWithCurrentReview = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      accountReviewed: state.accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    const accountReviewed = gateWithCurrentReview.accountPresenceNeedsReview ? false : state.accountReviewed
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { accountPresence, accountReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setMappingReviewed: (mappingReviewed) => set((state) => {
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      accountReviewed: state.accountReviewed,
      mappingReviewed,
    })
    return { mappingReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setBankKey: (bankKey) => set((state) => {
    const bankReviewed = false
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: bankKey,
      selectedAccount: state.account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: state.accountPresence,
      mapping: state.confirmedMapping,
      bankReviewed,
      accountReviewed: state.accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { bankKey, bankReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
  setAccount: (account) => set((state) => {
    const accountReviewed = false
    const gate = evaluateReviewGate({
      detectedBank: state.detectedBank,
      selectedBankKey: state.bankKey,
      selectedAccount: account,
      inferredAccount: state.identityGuess?.account,
      accountPresence: null,
      mapping: state.confirmedMapping,
      bankReviewed: state.bankReviewed,
      accountReviewed,
      mappingReviewed: state.mappingReviewed,
    })
    return { account, accountPresence: null, accountReviewed, isBlockedCase: gate.isBlockedCase, canProceedToConfig: gate.canProceedToConfig }
  }),
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
