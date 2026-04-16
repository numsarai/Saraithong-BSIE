# BSIE Frontend

> Updated for BSIE v4.1

React 19 + Vite 8 + TypeScript analyst interface for BSIE.

## Stack

- **React 19** with TypeScript
- **Vite 8** for dev server and bundling
- **Tailwind CSS 3** for styling
- **Zustand 5** for state management
- **TanStack React Query 5** for server state
- **react-i18next** for internationalization (Thai primary, English fallback)
- **Cytoscape.js** for graph visualization (LinkChart, AccountFlowGraph)
- **Recharts** for charts (TimelineChart)
- **sonner** for toast notifications
- **vitest** for testing

## Architecture

### Lazy-Loaded Pages

Four heavy pages are code-split via `React.lazy()`:

1. **Dashboard** -- case overview and statistics
2. **BankManager** -- bank template configuration
3. **BulkIntake** -- batch folder processing
4. **InvestigationDesk** -- 13-tab investigation workspace

The default flow is the 5-step intake wizard (loaded eagerly).

### Main User Flow (5-Step Wizard)

1. `Step1Upload.tsx` -- upload .xlsx, .xls, .ofx, .pdf, or image; receive detected bank, suggested mapping, sample rows
2. `Step2Map.tsx` -- review bank detection, confirm or edit mapping, use mapping memory
3. `Step3Config.tsx` -- configure subject account and account holder name
4. `Step4Processing.tsx` -- poll job progress, show pipeline status
5. `Step5Results.tsx` -- browse results, inspect exports

### Investigation Workspace (13 Tabs)

The InvestigationDesk provides the operational workspace:

1. Database -- status, backup/restore, settings
2. Files -- uploaded file registry
3. Parser Runs -- run history, re-processing
4. Accounts -- account registry, review
5. Search -- full transaction search with filters
6. Alerts -- alert dashboard and rule config
7. Cross-Account -- multi-account analysis
8. Link Chart -- interactive Cytoscape.js graph
9. Timeline -- temporal aggregation with Recharts
10. Duplicates -- duplicate group review
11. Matches -- match candidate review
12. Audit -- audit log and learning feedback
13. Exports -- export job management

Sub-components extracted under `components/investigation/`:
- `DatabaseTab.tsx`
- `AlertsTab.tsx`
- `CrossAccountTab.tsx`

### Graph Components

- `LinkChart.tsx` -- interactive Cytoscape.js graph explorer (replaces former GraphExplorer)
- `AccountFlowGraph.tsx` -- per-account flow visualization
- `TimelineChart.tsx` -- Recharts-based temporal chart
- `TimeWheel.tsx` -- time distribution visualization

## Main Files

- App shell: `src/App.tsx`
- Entry point: `src/main.tsx`
- Shared app state: `src/store.ts`
- API client layer: `src/api.ts`
- Sidebar navigation: `src/components/Sidebar.tsx`
- i18n translations: `src/locales/th.json`, `src/locales/en.json`
- UI primitives: `src/components/ui/`

## Internationalization

- Thai (`th.json`) is the primary language
- English (`en.json`) is the fallback
- All user-facing text goes through `useTranslation()` from react-i18next
- Translation keys are organized by feature domain

## API Coupling Rule

Keep frontend-to-backend coupling centralized in:

- `src/api.ts`

Do not scatter raw `fetch(...)` calls across components.

## Local Commands

Install:

```bash
npm install
```

Run dev server:

```bash
npm run dev
```

Run tests:

```bash
npm test
```

Build:

```bash
npm run build
```

## Testing Focus

Important test areas:

- mapping confirmation gates
- remembered-name behavior in Step 3
- progress polling behavior
- result rendering and override display
- Investigation Desk review/audit/backup flows
- alert dashboard rendering
- link chart node/edge interactions

Examples:

- `src/components/steps/Step2Map.test.tsx`
- `src/components/steps/Step3Config.test.tsx`
- `src/components/steps/Step5Results.test.tsx`
- `src/components/InvestigationDesk.test.tsx`
- `src/components/BankManager.test.tsx`
- `src/components/BulkIntake.test.tsx`
- `src/components/Sidebar.test.tsx`
