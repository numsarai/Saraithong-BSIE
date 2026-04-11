import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'
import i18n from '../i18n'

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
