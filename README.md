# SpendLens

SpendLens is a personal finance utility for tracking how much money is actually safe to spend when money moves across bank accounts, cash, wallets, UPI, credit cards, recurring expenses, EMI installments, and monthly investments.

Phase 2B adds obligation intelligence for amount-based recurring commitments and first-class credit-card EMI plan tracking. There is still no authentication, AI, statement ingestion, Gmail/SMS integration, bank API integration, PDF parsing, CSV import, transaction editing, or transaction deletion.

## Core Financial Rule

SpendLens uses a conservative safe-to-spend calculation:

```text
safe_to_spend =
  liquid_cash
  - credit_card_liability
  - remaining_fixed_commitments
  - remaining_emi_installments
  - remaining_savings_target
```

Future expected salary is never included. Income only affects the calculation after it is recorded as an actual income transaction with an `occurred_at` date on or before the calculation date.

If no financial profile exists yet, `monthly_savings_target` defaults to `0` for dashboard calculations.

## Obligation Semantics

Recurring fixed commitments are fulfilled by amount, not by the mere presence of a linked transaction. For each active fixed-expense commitment, SpendLens sums current app-local month linked expense transactions, derives `paid_amount_this_month`, and reserves only `max(commitment.amount - paid_amount_this_month, 0)`.

Commitment payment state is derived from the ledger and is not stored as a mutable paid flag. The status API reports `paid`, `partial`, `overdue_partial`, `upcoming`, `due_today`, or `overdue`. For paid commitments, `fulfilled_at` is the linked transaction that causes cumulative current-month payments to reach the commitment amount.

Investment transactions do not fulfill fixed-expense commitments. Existing linked-transaction validation still requires the transaction account, category, and type to match the recurring commitment.

Recurring commitments can be corrected or deactivated. Editing a commitment changes its current obligation configuration but does not rewrite existing linked transactions.

## EMI Plans

Credit-card EMIs are tracked as EMI plans, separate from recurring commitments. This avoids mixing two different concepts:

- `monthly_installment`: the installment that may post to the credit card this month.
- `remaining_amount_at_setup`: the total EMI amount still remaining when the plan is created.

The EMI plan account must be a credit-card account. The category is selected by the user and is not hardcoded.

At setup, the current month installment state prevents double counting:

- `not_posted`: the current installment has not posted to the card yet, so it is reserved in Safe to Spend.
- `included_in_opening_liability`: the current installment is already represented in card liability, so it is not reserved again.
- `settled_before_tracking`: the current installment was already handled before SpendLens tracking, so it is not reserved.

An unposted EMI installment is reserved. Once the installment posts as a linked credit-card expense, the EMI reserve disappears and card liability carries the obligation. A bank-to-credit-card transfer is still the separate card bill payment.

SpendLens does not subtract the total future EMI balance from Safe to Spend. It only subtracts the current month unrecognized installment reserve.

EMI installment recognition is chronological. A later installment cannot be posted while an earlier required month is unrecognized, and SpendLens carries the earliest unrecognized installment forward as the actionable EMI obligation.

## Architecture

- Backend: Python, FastAPI, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, Alembic, Decimal money calculations.
- Frontend: Next.js 16, App Router, TypeScript, ESLint, React state, normal CSS.
- Docker Compose runs `web`, `api`, and `db` for local MVP usage.

Business calculations live in `backend/app/services`. The frontend does not duplicate financial formulas; it displays values returned by the FastAPI API.

## Continuous Integration

GitHub Actions runs backend pytest, frontend ESLint, and the frontend production build on pushes and pull requests for `master`.

## Frontend

The frontend focuses on manual personal finance tracking:

- Dashboard safe-to-spend hero with a breakdown for liquid cash, card liability, fixed commitments left, EMI installments left, savings target left, and Safe to Spend.
- Monthly obligations section with derived fixed-commitment status and payment prefill links.
- Credit-card exposure cards using backend `/api/v1/cards/exposure` values.
- Recent transactions and full transaction history with linked commitment and EMI plan labels.
- Manual transaction entry for expense, income, transfer, investment, refund, recurring commitment payments, and EMI installment postings.
- Account creation for bank, cash, wallet, and credit-card accounts.
- Financial profile, recurring commitment setup, and EMI plan setup.
- Mobile-first layout with desktop sidebar and mobile bottom navigation.

Application routes:

- `/` Dashboard
- `/transactions` Add transaction and transaction history filters
- `/accounts` Account setup and card exposure
- `/settings` Financial profile, recurring commitments, and EMI plans

## Environment Variables

Root `.env` for FastAPI:

```text
DATABASE_URL=postgresql+psycopg://spendlens:spendlens@localhost:5432/spendlens
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
APP_TIMEZONE=Asia/Kolkata
```

Frontend `.env.local`:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

`NEXT_PUBLIC_API_BASE_URL` must be the browser-facing FastAPI base URL. In Docker Compose it is set to `http://localhost:8000`, not `http://api:8000`, because browser requests resolve from the host.

## Timezone Contract

`APP_TIMEZONE` defines the application financial calendar. The default is `Asia/Kolkata`.

Transaction timestamps are stored internally as timezone-naive UTC datetimes. Timezone-aware API input is converted to UTC before storage; timezone-naive API input is interpreted in `APP_TIMEZONE`, then converted to UTC. The manual frontend datetime input is converted from browser-local time to a UTC ISO timestamp before submission.

Financial day, month, transaction date-filter, commitment status, EMI status, and card billing-cycle boundaries are evaluated in `APP_TIMEZONE` and converted to UTC-naive database query boundaries.

## Backend Local Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy ..\.env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

## Frontend Local Setup

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

The frontend runs at `http://localhost:3000`.

## Docker Setup

```bash
docker compose up --build
```

Services:

- `db`: PostgreSQL on `localhost:5432`
- `api`: FastAPI on `http://127.0.0.1:8000`
- `web`: Next.js on `http://localhost:3000`

Seed initial categories after the API is up:

```bash
docker compose exec api python -m app.seed
```

The seed command is idempotent and does not create duplicate categories.

## Manual Transaction Workflow

Amounts are always positive. Do not send signed transaction amounts. Send money values as strings when cents are involved, for example `"123.45"`, so API validation never has to accept Python floats.

Credit-card purchase:

```text
transaction_type = expense
source_account = credit card
```

This is counted as spending immediately and increases card outstanding.

Credit-card bill payment:

```text
transaction_type = transfer
source_account = bank/cash/wallet account
destination_account = credit card
```

This reduces liquid cash and reduces card liability. It is not another expense, which prevents double-counting.

EMI installment posting:

```text
transaction_type = expense
source_account = EMI plan credit card
category = EMI plan category
emi_plan_id = EMI plan id
```

This records the EMI installment posting to the credit card and increases card liability. Paying the card bill remains a separate bank-to-credit-card transfer.

Credit cards cannot be transfer source accounts in this phase. Credit-card cash advances and balance transfers are not modeled.

Investments reduce liquid cash and count toward the monthly savings target. Credit cards cannot be used as the source account for investment transactions.

Transfers between bank, cash, and wallet accounts move money but do not count as spending.

When a transaction links to a recurring commitment, it must match the commitment's configured account, category, and commitment type. Fixed-expense commitments can only link to expense transactions; investment commitments can only link to investment transactions.

A transaction may link to either a recurring commitment or an EMI plan, never both. EMI-linked transactions must match the EMI plan card, category, expected installment amount, and app-local month uniqueness rules.

## Credit Card Handling

For credit cards:

```text
raw_outstanding =
  opening_outstanding
  + card expenses
  - refunds to card
  - transfers received by card
```

Financial exposure reports liability as `max(raw_outstanding, 0)`. If a card is overpaid, raw outstanding may be negative internally, but liability is clamped to zero and overpaid credit is not counted as liquid cash.

## API Endpoints

- `GET /health`
- `POST /api/v1/accounts`
- `GET /api/v1/accounts`
- `GET /api/v1/accounts/{account_id}`
- `POST /api/v1/categories`
- `GET /api/v1/categories`
- `POST /api/v1/transactions`
- `GET /api/v1/transactions`
- `POST /api/v1/commitments`
- `GET /api/v1/commitments`
- `GET /api/v1/commitments/status`
- `POST /api/v1/emi-plans`
- `GET /api/v1/emi-plans`
- `GET /api/v1/emi-plans/status`
- `GET /api/v1/emi-plans/{emi_plan_id}`
- `PUT /api/v1/financial-profile`
- `GET /api/v1/financial-profile`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/cards/exposure`

`GET /api/v1/transactions` supports optional filters: `account_id`, `transaction_type`, `category_id`, `date_from`, and `date_to`.

Dashboard, card exposure, commitment status, and EMI status endpoints accept an optional `as_of=YYYY-MM-DD` query parameter for deterministic calculations. If omitted, the API uses the current application-local date.

## Initial Categories

Run `python -m app.seed` from `backend/` to create:

Food, Housing, EMI, Subscription, Shopping, Travel, Recharge, Investment, Gift, Miscellaneous, Salary.

## Tests and Validation

Backend:

```bash
python -m pytest backend/tests -v
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```
