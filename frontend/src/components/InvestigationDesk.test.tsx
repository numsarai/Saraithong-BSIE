import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { InvestigationDesk } from '@/components/InvestigationDesk'

vi.mock('@/api', () => ({
  createDatabaseBackup: vi.fn(async () => ({ filename: 'backup.json', pruned_backups: [] })),
  createExportJob: vi.fn(async () => ({ id: 'EXP-1' })),
  getAccountDetail: vi.fn(async () => null),
  getAccounts: vi.fn(async () => ({ items: [] })),
  getAuditLogs: vi.fn(async () => ({
    items: [
      {
        id: 'AUD-1',
        object_type: 'transaction',
        object_id: 'TXN-001',
        action_type: 'update',
        changed_by: 'analyst',
        changed_at: '2026-03-30T23:30:00Z',
      },
    ],
  })),
  getLearningFeedbackLogs: vi.fn(async () => ({
    items: [
      {
        id: 'LF-1',
        object_type: 'learning_feedback',
        object_id: 'mapping_profile:PROFILE-1',
        action_type: 'mapping_confirmation',
        changed_by: 'analyst',
        changed_at: '2026-03-31T01:30:00Z',
        extra_context_json: {
          learning_domain: 'mapping_memory',
          feedback_status: 'corrected',
          source_object_type: 'mapping_profile',
          source_object_id: 'PROFILE-1',
        },
      },
      {
        id: 'LF-2',
        object_type: 'learning_feedback',
        object_id: 'account:ACC-1',
        action_type: 'account_review_identity',
        changed_by: 'analyst',
        changed_at: '2026-03-30T22:00:00Z',
        extra_context_json: {
          learning_domain: 'account_identity',
          feedback_status: 'confirmed',
          source_object_type: 'account',
          source_object_id: 'ACC-1',
        },
      },
    ],
  })),
  getDatabaseBackupPreview: vi.fn(async () => ({ counts: {} })),
  getDatabaseBackups: vi.fn(async () => ({ items: [], reset_confirmation_text: 'RESET BSIE DATABASE', restore_confirmation_text: 'RESTORE BSIE DATABASE' })),
  getDatabaseBackupSettings: vi.fn(async () => ({ enabled: false, interval_hours: 24, backup_format: 'json', effective_backup_format: 'json', retention_enabled: false, retain_count: 20, source: 'environment_defaults' })),
  getDbStatus: vi.fn(async () => ({ database_backend: 'sqlite', database_runtime_source: 'local_sqlite', table_count: 22, has_investigation_schema: true, key_record_counts: {}, tables: [], database_url_masked: 'sqlite:///bsie.db' })),
  getDuplicates: vi.fn(async () => ({ items: [] })),
  getExportJobs: vi.fn(async () => ({ items: [] })),
  getFileDetail: vi.fn(async () => null),
  getFiles: vi.fn(async () => ({
    items: [
      {
        id: 'FILE-1',
        original_filename: 'sample.xlsx',
        import_status: 'stored',
        uploaded_at: '2026-03-30T23:30:00Z',
        file_hash_sha256: '1234567890abcdef1234567890abcdef',
      },
    ],
  })),
  getGraphDerivedEdges: vi.fn(async () => ({ items: [] })),
  getGraphAnalysis: vi.fn(async () => ({
    overview: {
      transaction_rows: 12,
      business_node_count: 5,
      business_edge_count: 4,
      connected_components: 2,
      review_candidate_nodes: 1,
      suggested_match_edges: 1,
      suspicious_finding_count: 2,
      top_node_by_degree: { label: 'Subject Account' },
      top_node_by_flow: { label: 'Alice (2222222222)' },
    },
    top_nodes_by_degree: [
      { node_id: 'ACCOUNT:1111111111', label: 'Subject Account', node_type: 'Account', degree: 4, in_degree: 2, out_degree: 2, total_flow_value: 1500 },
    ],
    review_candidates: [
      { node_id: 'PARTIAL_ACCOUNT:12345', label: 'Partial 12345', node_type: 'PartialAccount', reason_count: 2, reason_codes: 'partial_account_only|review_pending' },
    ],
    connected_components: [
      { component_id: 'COMP-001', size: 3, node_labels: 'Subject Account|Alice (2222222222)|Partial 12345' },
    ],
    lineage_summary: { file_count: 1, parser_run_count: 1 },
    query_meta: { cache_hit: true, transactions_loaded: 0, truncated: false },
  })),
  getGraphEdges: vi.fn(async () => ({ items: [] })),
  getGraphFindings: vi.fn(async () => ({
    items: [
      {
        finding_id: 'F-1',
        severity: 'high',
        summary: 'High fan-in into ACCOUNT:1111111111',
        subject_node_ids: 'ACCOUNT:1111111111|ACCOUNT:2222222222',
        reason_codes: 'fan_in|multi_source',
      },
    ],
  })),
  getGraphNeighborhood: vi.fn(async () => ({
    center_node_id: 'ACCOUNT:1111111111',
    nodes: [
      {
        node_id: 'ACCOUNT:1111111111',
        label: 'Subject Account',
        node_type: 'Account',
        review_status: 'pending',
        source_transaction_ids: 'TXN-1|TXN-2',
        source_files: 'statement.xlsx',
      },
      {
        node_id: 'ACCOUNT:2222222222',
        label: 'Alice (2222222222)',
        node_type: 'Account',
        review_status: '',
        source_transaction_ids: 'TXN-1',
        source_files: 'statement.xlsx',
      },
    ],
    edges: [
      {
        edge_id: 'DERIVED-1',
        from_node_id: 'ACCOUNT:2222222222',
        to_node_id: 'ACCOUNT:1111111111',
        edge_type: 'DERIVED_ACCOUNT_TO_ACCOUNT',
      },
    ],
    suspicious_node_ids: ['ACCOUNT:1111111111'],
    findings: [
      {
        finding_id: 'F-1',
        severity: 'high',
        rule_type: 'fan_in_accounts',
        summary: 'High fan-in into ACCOUNT:1111111111',
        subject_node_ids: 'ACCOUNT:1111111111|ACCOUNT:2222222222',
      },
    ],
    findings_by_node: {
      'ACCOUNT:1111111111': [
        {
          finding_id: 'F-1',
          severity: 'high',
          rule_type: 'fan_in_accounts',
          summary: 'High fan-in into ACCOUNT:1111111111',
        },
      ],
    },
    query_meta: { cache_hit: true, transactions_loaded: 0, truncated: false },
    graph_meta: { hidden_node_count: 0, hidden_node_ids: [], hidden_findings_count: 0 },
  })),
  getGraphNeo4jStatus: vi.fn(async () => ({
    enabled: false,
    configured: false,
    driver_available: false,
    driver_version: '',
    uri_masked: '',
  })),
  getGraphNodes: vi.fn(async () => ({
    items: [
      { node_id: 'ACCOUNT:1111111111', label: 'Subject Account', node_type: 'Account', review_status: 'pending' },
      { node_id: 'ACCOUNT:2222222222', label: 'Alice (2222222222)', node_type: 'Account', review_status: '' },
    ],
    meta: { transactions_loaded: 0, cache_hit: false, truncated: false },
  })),
  getMatches: vi.fn(async () => ({ items: [] })),
  getParserRunDetail: vi.fn(async () => null),
  getParserRuns: vi.fn(async () => ({
    items: [
      {
        id: 'RUN-1',
        status: 'done',
        bank_detected: 'SCB',
        started_at: '2026-03-30T23:30:00Z',
      },
    ],
  })),
  getTransactionDetail: vi.fn(async () => null),
  reprocessParserRun: vi.fn(async () => ({ job_id: 'JOB-1' })),
  resetDatabase: vi.fn(async () => ({ status: 'ok' })),
  restoreDatabase: vi.fn(async () => ({ restored_backup: 'backup.json' })),
  syncGraphToNeo4j: vi.fn(async () => ({ status: 'ok', node_count: 2, edge_count: 1, derived_edge_count: 0 })),
  updateDatabaseBackupSettings: vi.fn(async () => ({ enabled: false, interval_hours: 24, backup_format: 'json', effective_backup_format: 'json', retention_enabled: false, retain_count: 20, source: 'database' })),
  getLlmStatus: vi.fn(async () => ({ status: 'ok', model_roles: { text: 'qwen3.5:9b' }, models: ['qwen3.5:9b'] })),
  llmChat: vi.fn(async () => ({ response: 'ok' })),
  listCaseTags: vi.fn(async () => ({
    items: [
      {
        id: 'CASE-TAG-1',
        tag: 'CASE-ALPHA',
        description: 'Alpha evidence group',
        created_at: '2026-03-31T02:00:00Z',
        linked_object_count: 2,
        linked_object_counts: { transaction: 1, alert: 1 },
      },
      {
        id: 'CASE-TAG-2',
        tag: 'CASE-BETA',
        description: 'Beta account group',
        created_at: '2026-03-31T03:00:00Z',
        linked_object_count: 1,
        linked_object_counts: { account: 1 },
      },
    ],
  })),
  getCaseTagDetail: vi.fn(async () => ({
    id: 'CASE-TAG-1',
    tag: 'CASE-ALPHA',
    description: 'Alpha evidence group',
    created_at: '2026-03-31T02:00:00Z',
    linked_object_count: 2,
    linked_object_counts: { transaction: 1, alert: 1 },
    links: [
      {
        link_id: 'LINK-TX-1',
        object_type: 'transaction',
        object_id: 'TX-1',
        citation_id: 'txn:TX-1',
        found: true,
        label: 'OUT 1,000.00 THB',
        summary: 'Transfer to suspect',
        scope: { parser_run_id: 'RUN-1', file_id: 'FILE-1' },
      },
    ],
  })),
  askCopilot: vi.fn(async () => ({
    status: 'ok',
    source: 'local_llm_investigation_copilot',
    read_only: true,
    mutations_allowed: false,
    model: 'qwen3.5:9b',
    task_mode: 'account_summary',
    answer: 'พบรายการออกสำคัญ [txn:TX-1]',
    scope: { parser_run_id: 'RUN-1', file_id: '', account: '', account_digits: '', case_tag_id: '', case_tag: '' },
    context_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    prompt_hash: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    citation_policy: { status: 'ok', requires_review: false, warning: '' },
    citations: [{ id: 'txn:TX-1', type: 'txn', object_id: 'TX-1', label: 'OUT 1,000.00 THB' }],
    warnings: [],
    audit_id: 'AUDIT-COPILOT-1',
    usage: { prompt_tokens: 10, completion_tokens: 5 },
  })),
  previewClassification: vi.fn(async () => ({
    status: 'ok',
    source: 'local_llm_classification_preview',
    read_only: true,
    mutations_allowed: false,
    provider: 'local',
    model: 'qwen3.5:9b',
    total: 1,
    suggestion_count: 1,
    review_count: 1,
    min_confidence: 0.85,
    items: [
      {
        transaction_id: 'TXN-PREVIEW-1',
        direction: 'OUT',
        amount: -500,
        description: 'ATM WDL 1234567890',
        current: { transaction_type: 'OUT_TRANSFER', confidence: 0.8, counterparty_name: '' },
        ai: { transaction_type: 'WITHDRAW', confidence: 0.91, counterparty_name: 'ATM Withdrawal' },
        suggested: { transaction_type: 'WITHDRAW', confidence: 0.91, counterparty_name: 'ATM Withdrawal' },
        review_required: true,
        would_apply: true,
        action: 'review_divergence',
        reason: 'ai_type_differs_from_current',
      },
    ],
    warnings: [],
  })),
  reviewAccount: vi.fn(async () => ({ status: 'ok' })),
  reviewDuplicate: vi.fn(async () => ({ status: 'ok' })),
  reviewMatch: vi.fn(async () => ({ status: 'ok' })),
  reviewTransaction: vi.fn(async () => ({ status: 'ok' })),
  searchTransactionRecords: vi.fn(async () => ({ items: [] })),
}))

const { askCopilot, createExportJob, getAuditLogs, getLearningFeedbackLogs, previewClassification, reviewTransaction, searchTransactionRecords } = await import('@/api')
const { useStore } = await import('@/store')

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <InvestigationDesk />
    </QueryClientProvider>
  )
}

describe('InvestigationDesk date formatting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    useStore.setState({ operatorName: 'Case Reviewer' })
  })

  it('renders file, parser run, and audit dates as DD MM YYYY', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'Files' }))
    expect((await screen.findAllByText('31 03 2026')).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Parser Runs' }))
    expect((await screen.findAllByText('31 03 2026')).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Audit' }))
    expect((await screen.findAllByText('31 03 2026')).length).toBeGreaterThan(0)
  })

  it('offers a learning feedback shortcut in the audit tab', async () => {
    vi.mocked(getAuditLogs).mockImplementation(async (params?: Record<string, unknown>) => {
      if (params?.object_type === 'learning_feedback') {
        return {
          items: [
            {
              id: 'LF-1',
              object_type: 'learning_feedback',
              object_id: 'mapping_profile:PROFILE-1',
              action_type: 'mapping_confirmation',
              changed_by: 'analyst',
              changed_at: '2026-03-31T01:30:00Z',
              extra_context_json: {
                learning_domain: 'mapping_memory',
                feedback_status: 'corrected',
                source_object_type: 'mapping_profile',
                source_object_id: 'PROFILE-1',
              },
            },
          ],
        }
      }
      return {
        items: [
          {
            id: 'AUD-1',
            object_type: 'transaction',
            object_id: 'TXN-001',
            action_type: 'update',
            changed_by: 'analyst',
            changed_at: '2026-03-30T23:30:00Z',
          },
        ],
      }
    })

    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'Audit' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Learning Feedback' }))

    await waitFor(() => expect(getAuditLogs).toHaveBeenLastCalledWith({ object_type: 'learning_feedback', object_id: '', limit: 100 }))
    await waitFor(() => expect(getLearningFeedbackLogs).toHaveBeenCalledWith({ limit: 200 }))
    expect(await screen.findByText('Learning Feedback Summary')).toBeInTheDocument()
    expect(await screen.findByText('mapping_memory (1) · account_identity (1)')).toBeInTheDocument()
    expect(await screen.findByText('source mapping_profile:PROFILE-1')).toBeInTheDocument()
    expect((await screen.findAllByText('Corrected')).length).toBeGreaterThan(0)
  })

  it('uses the stored operator name for graph exports', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'Graph Export' }))

    await waitFor(() => expect(createExportJob).toHaveBeenCalledWith({
      export_type: 'graph',
      filters: {},
      created_by: 'Case Reviewer',
    }))
  })

  it('asks the investigation copilot with a scoped parser run and shows citations', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Parser Run ID'), { target: { value: 'RUN-1' } })
    fireEvent.change(screen.getByLabelText('Analyst focus'), { target: { value: 'Summarize this scope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask Copilot' }))

    await waitFor(() => expect(askCopilot).toHaveBeenCalledWith({
      question: 'Summarize this scope',
      task_mode: 'account_summary',
      scope: { parser_run_id: 'RUN-1', file_id: '', account: '', case_tag_id: '', case_tag: '' },
      operator: 'Case Reviewer',
      max_transactions: 20,
    }))
    expect(await screen.findByText('พบรายการออกสำคัญ [txn:TX-1]')).toBeInTheDocument()
    expect(await screen.findByText('txn:TX-1')).toBeInTheDocument()
    expect(await screen.findByText('AUDIT-COPILOT-1')).toBeInTheDocument()
  })

  it('uses the case tag picker for evidence copilot scope', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Filter Case Tags'), { target: { value: 'alpha' } })
    expect(await screen.findByRole('option', { name: 'CASE-ALPHA' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'CASE-BETA' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Choose Case Tag'), { target: { value: 'CASE-TAG-1' } })
    expect(await screen.findByText('Alpha evidence group')).toBeInTheDocument()
    expect(await screen.findByText('2 linked · alert 1 · transaction 1')).toBeInTheDocument()
    expect(await screen.findByText('txn:TX-1')).toBeInTheDocument()
    expect(await screen.findByText('OUT 1,000.00 THB')).toBeInTheDocument()
    expect(await screen.findByText('Transfer to suspect')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Focus scope' }))
    fireEvent.change(screen.getByLabelText('Analyst focus'), { target: { value: 'Review tagged evidence' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask Copilot' }))

    await waitFor(() => expect(askCopilot).toHaveBeenCalledWith({
      question: 'Review tagged evidence',
      task_mode: 'account_summary',
      scope: { parser_run_id: 'RUN-1', file_id: 'FILE-1', account: '', case_tag_id: 'CASE-TAG-1', case_tag: 'CASE-ALPHA' },
      operator: 'Case Reviewer',
      max_transactions: 20,
    }))
  })

  it('previews local classification suggestions without applying them', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Preview Description'), { target: { value: 'ATM WDL 1234567890' } })
    fireEvent.click(screen.getByRole('button', { name: 'Preview Classification' }))

    await waitFor(() => expect(previewClassification).toHaveBeenCalledWith({
      transactions: [
        {
          transaction_id: 'TXN-PREVIEW-1',
          date: '',
          direction: 'OUT',
          amount: 0,
          description_raw: 'ATM WDL 1234567890',
          transaction_type: 'OUT_TRANSFER',
          confidence: 0.8,
          counterparty_name: '',
        },
      ],
    }))
    expect(await screen.findByText('review_divergence')).toBeInTheDocument()
    expect(await screen.findByText('ai_type_differs_from_current')).toBeInTheDocument()
    expect((await screen.findAllByText('WITHDRAW')).length).toBeGreaterThanOrEqual(2)
    expect((await screen.findAllByText('ATM Withdrawal')).length).toBeGreaterThanOrEqual(2)
  })

  it('previews classification from selected scoped transactions', async () => {
    vi.mocked(searchTransactionRecords).mockResolvedValueOnce({
      items: [
        {
          id: 'TXN-SCOPE-1',
          parser_run_id: 'RUN-1',
          transaction_datetime: '2026-01-01T08:00:00Z',
          amount: -900,
          direction: 'OUT',
          description_normalized: 'ATM WDL 1234567890',
          transaction_type: 'OUT_TRANSFER',
          confidence: 0.76,
          channel: 'ATM',
          counterparty_account_normalized: '1234567890',
          counterparty_name_normalized: 'ATM',
        },
      ],
    })
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Parser Run ID'), { target: { value: 'RUN-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Load Scoped Transactions' }))

    await waitFor(() => expect(searchTransactionRecords).toHaveBeenCalledWith({
      parser_run_id: 'RUN-1',
      file_id: '',
      account: '',
      limit: 20,
      offset: 0,
    }))
    expect(await screen.findByText('TXN-SCOPE-1')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Select transaction TXN-SCOPE-1'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Selected' }))

    await waitFor(() => expect(previewClassification).toHaveBeenCalledWith({
      transactions: [
        {
          transaction_id: 'TXN-SCOPE-1',
          date: '2026-01-01T08:00:00Z',
          direction: 'OUT',
          amount: -900,
          description: 'ATM WDL 1234567890',
          description_normalized: 'ATM WDL 1234567890',
          description_raw: 'ATM WDL 1234567890',
          channel: 'ATM',
          counterparty_account: '1234567890',
          counterparty_name: 'ATM',
          transaction_type: 'OUT_TRANSFER',
          confidence: 0.76,
        },
      ],
    }))
    expect(await screen.findByText('review_divergence')).toBeInTheDocument()
  })

  it('applies selected classification suggestions through the audited review endpoint', async () => {
    vi.mocked(searchTransactionRecords)
      .mockResolvedValueOnce({
        items: [
          {
            id: 'TXN-SCOPE-1',
            parser_run_id: 'RUN-1',
            transaction_datetime: '2026-01-01T08:00:00Z',
            amount: -900,
            direction: 'OUT',
            description_normalized: 'ATM WDL 1234567890',
            transaction_type: 'OUT_TRANSFER',
            confidence: 0.76,
          },
        ],
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'TXN-SCOPE-1',
            parser_run_id: 'RUN-1',
            transaction_datetime: '2026-01-01T08:00:00Z',
            amount: -900,
            direction: 'OUT',
            description_normalized: 'ATM WDL 1234567890',
            transaction_type: 'WITHDRAW',
            counterparty_name_normalized: 'ATM Withdrawal',
            confidence: 0.76,
          },
        ],
      })
    vi.mocked(previewClassification).mockResolvedValueOnce({
      status: 'ok',
      source: 'local_llm_classification_preview',
      read_only: true,
      mutations_allowed: false,
      provider: 'local',
      model: 'qwen3.5:9b',
      total: 1,
      suggestion_count: 1,
      review_count: 1,
      min_confidence: 0.85,
      items: [
        {
          transaction_id: 'TXN-SCOPE-1',
          direction: 'OUT',
          amount: -900,
          description: 'ATM WDL 1234567890',
          current: { transaction_type: 'OUT_TRANSFER', confidence: 0.76, counterparty_name: '' },
          ai: { transaction_type: 'WITHDRAW', confidence: 0.91, counterparty_name: 'ATM Withdrawal' },
          suggested: { transaction_type: 'WITHDRAW', confidence: 0.91, counterparty_name: 'ATM Withdrawal' },
          review_required: true,
          would_apply: true,
          action: 'review_divergence',
          reason: 'ai_type_differs_from_current',
        },
      ],
      warnings: [],
    })
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Parser Run ID'), { target: { value: 'RUN-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Load Scoped Transactions' }))
    expect(await screen.findByText('TXN-SCOPE-1')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Select transaction TXN-SCOPE-1'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview Selected' }))

    expect(await screen.findByText('Review and Apply')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Select suggestion TXN-SCOPE-1'))
    fireEvent.change(screen.getByLabelText('Apply Reason'), { target: { value: 'Accepted ATM classification after analyst review' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply Selected Suggestions' }))

    await waitFor(() => expect(reviewTransaction).toHaveBeenCalledWith('TXN-SCOPE-1', {
      reviewer: 'Case Reviewer',
      reason: 'Accepted ATM classification after analyst review',
      changes: {
        transaction_type: 'WITHDRAW',
        counterparty_name_normalized: 'ATM Withdrawal',
      },
    }))
    await waitFor(() => expect(searchTransactionRecords).toHaveBeenCalledTimes(2))
    expect(searchTransactionRecords).toHaveBeenLastCalledWith({
      parser_run_id: 'RUN-1',
      file_id: '',
      account: '',
      limit: 20,
      offset: 0,
    })
    expect(await screen.findByText('Applied 1 suggestion(s) with audit trail and refreshed scoped rows.')).toBeInTheDocument()
    expect(await screen.findByText('Applied History')).toBeInTheDocument()
    expect(await screen.findByText('transaction_type: WITHDRAW · counterparty_name_normalized: ATM Withdrawal')).toBeInTheDocument()
  })

  it('loads classification audit history and reverts changes through review', async () => {
    vi.mocked(searchTransactionRecords)
      .mockResolvedValueOnce({
        items: [
          {
            id: 'TXN-SCOPE-1',
            parser_run_id: 'RUN-1',
            transaction_datetime: '2026-01-01T08:00:00Z',
            amount: -900,
            direction: 'OUT',
            description_normalized: 'ATM WDL 1234567890',
            transaction_type: 'WITHDRAW',
            counterparty_name_normalized: 'ATM Withdrawal',
            confidence: 0.76,
          },
        ],
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'TXN-SCOPE-1',
            parser_run_id: 'RUN-1',
            transaction_datetime: '2026-01-01T08:00:00Z',
            amount: -900,
            direction: 'OUT',
            description_normalized: 'ATM WDL 1234567890',
            transaction_type: 'OUT_TRANSFER',
            confidence: 0.76,
          },
        ],
      })
    vi.mocked(getAuditLogs).mockResolvedValue({
      items: [
        {
          id: 'AUD-CLASS-1',
          object_type: 'transaction',
          object_id: 'TXN-SCOPE-1',
          action_type: 'field_update',
          field_name: 'transaction_type',
          old_value_json: 'OUT_TRANSFER',
          new_value_json: 'WITHDRAW',
          changed_by: 'Case Reviewer',
          changed_at: '2026-01-01T09:00:00Z',
          reason: 'Accepted ATM classification after analyst review',
        },
      ],
    })
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'AI Copilot' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evidence' }))
    fireEvent.change(screen.getByLabelText('Parser Run ID'), { target: { value: 'RUN-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Load Scoped Transactions' }))
    expect(await screen.findByText('TXN-SCOPE-1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Load Audit History' }))

    await waitFor(() => expect(getAuditLogs).toHaveBeenCalledWith({
      object_type: 'transaction',
      object_id: 'TXN-SCOPE-1',
      limit: 20,
    }))
    expect(await screen.findByText('OUT_TRANSFER -> WITHDRAW')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Revert Reason'), { target: { value: 'Undo after audit review' } })
    fireEvent.click(screen.getByRole('button', { name: 'Revert Change' }))

    await waitFor(() => expect(reviewTransaction).toHaveBeenCalledWith('TXN-SCOPE-1', {
      reviewer: 'Case Reviewer',
      reason: 'Undo after audit review',
      changes: {
        transaction_type: 'OUT_TRANSFER',
      },
    }))
    await waitFor(() => expect(searchTransactionRecords).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Reverted transaction_type on TXN-SCOPE-1 with audit trail.')).toBeInTheDocument()
  })
})
