import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

function createMemoryStorage(): Storage {
  const store = new Map<string, string>()

  return {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(String(key), String(value))
    },
  }
}

const localStorageStub = createMemoryStorage()
const sessionStorageStub = createMemoryStorage()

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageStub,
})

Object.defineProperty(globalThis, 'sessionStorage', {
  configurable: true,
  value: sessionStorageStub,
})

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: localStorageStub,
  })

  Object.defineProperty(window, 'sessionStorage', {
    configurable: true,
    value: sessionStorageStub,
  })
}

const { default: i18n } = await import('../i18n')

// Tests were written with English strings, so force English locale for tests
i18n.changeLanguage('en')

// Mock cytoscape (requires canvas which isn't available in jsdom)
vi.mock('cytoscape', () => ({
  default: () => ({
    destroy: vi.fn(),
    getElementById: () => ({ length: 0, lock: vi.fn() }),
    fit: vi.fn(),
  }),
}))

// Mock AccountFlowGraph to avoid fetch/cytoscape issues in tests
vi.mock('../components/AccountFlowGraph', () => ({
  AccountFlowGraph: () => null,
}))
