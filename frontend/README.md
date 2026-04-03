# BSIE Frontend

This directory contains the React + TypeScript + Vite analyst interface for BSIE.

## What The Frontend Actually Does

BSIE is not a generic single-page shell. The frontend has four real surfaces:

1. Main intake wizard
2. Bank Manager
3. Bulk Intake
4. Investigation Admin

Navigation between those surfaces is controlled by Zustand state in [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts).

## Main User Flow

The default analyst flow is a 5-step wizard:

1. [`Step1Upload.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step1Upload.tsx)
   - upload `.xlsx`, `.xls`, or `.ofx`
   - receive detected bank, suggested mapping, sample rows, and identity hints
2. [`Step2Map.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step2Map.tsx)
   - review bank detection
   - confirm or edit mapping
   - use mapping memory and bank fingerprint memory
   - pass explicit analyst confirmation back to the backend
3. [`Step3Config.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step3Config.tsx)
   - configure subject account and account holder name
   - surface remembered account names from prior ingests before processing
4. [`Step4Processing.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step4Processing.tsx)
   - poll job progress and show pipeline logs/status
5. [`Step5Results.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step5Results.tsx)
   - browse transaction results
   - inspect exports and override effects

## Main Files

- App shell: [`/Users/saraithong/Documents/bsie/frontend/src/App.tsx`](/Users/saraithong/Documents/bsie/frontend/src/App.tsx)
- Entry point: [`/Users/saraithong/Documents/bsie/frontend/src/main.tsx`](/Users/saraithong/Documents/bsie/frontend/src/main.tsx)
- Shared app state: [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)
- API client layer: [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)
- Sidebar navigation: [`/Users/saraithong/Documents/bsie/frontend/src/components/Sidebar.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/Sidebar.tsx)
- Investigation Admin: [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)
- Bulk Intake: [`/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx)
- Bank template management: [`/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx)

## Investigation Admin

The investigation surface is not just a debug page. It is the operational workspace for:

- database status and backup controls
- files and parser runs
- account and transaction review
- duplicate and match review
- audit and learning-feedback inspection
- graph analysis and export jobs

Primary file:
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

## API Coupling Rule

Keep frontend-to-backend coupling centralized in:

- [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)

Do not scatter raw `fetch(...)` calls across many components unless there is a very strong reason.

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
npm test -- --run
```

Build:

```bash
npm run build
```

## Frontend Testing Focus

Important test areas:

- mapping confirmation gates
- remembered-name behavior in Step 3
- progress polling behavior
- result rendering and override display
- Investigation Desk review/audit/backup flows

Examples:

- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step2Map.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step2Map.test.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step3Config.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step3Config.test.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step5Results.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step5Results.test.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.test.tsx)
