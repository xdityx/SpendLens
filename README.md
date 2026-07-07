# SpendLens

SpendLens is a personal finance utility for tracking how much money is actually safe to spend when money moves across bank accounts, cash, wallets, UPI, credit cards, recurring expenses, and monthly investments.

Phase 2A adds a manual usability frontend for everyday transaction entry. There is still no authentication, AI, statement ingestion, Gmail/SMS integration, bank API integration, PDF parsing, or CSV import.

## Core Financial Rule

SpendLens uses a conservative safe-to-spend calculation:

```text
safe_to_spend =
  liquid_cash
  - credit_card_liability
  - remaining_fixed_commitments
  - remaining_savings_target
```

Future expected salary is never included. Income only affects the calculation after it is recorded as an actual income transaction with an `occurred_at` date on or before the calculation date.

If no financial profile exists yet, `monthly_savings_target` defaults to `0` for dashboard calculations.

## Architecture

- Backend: Python, FastAPI, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, Alembic, Decimal money calculations.
- Frontend: Next.js 16, App Router, TypeScript, ESLint, React state, normal CSS.
- Docker Compose runs `web`, `api`, and `db` for local MVP usage.

Business calculations live in `backend/app/services`. The frontend does not duplicate financial formulas; it displays values returned by the FastAPI API.

## Phase 2A Frontend

The frontend focuses on manual personal finance tracking:

- Dashboard safe-to-spend hero with liquid cash, card liability, fixed commitments left, and savings target left.
- Credit-card exposure cards using backend `/api/v1/cards/exposure` values.
- Recent transactions and full transaction history.
- Manual transaction entry for expense, income, transfer, investment, and refund.
- Account creation for bank, cash, wallet, and credit-card accounts.
- Financial profile and recurring commitment setup.
- Mobile-first layout with desktop sidebar and mobile bottom navigation.

Application routes:

- `/` Dashboard
- `/transactions` Add transaction and transaction history filters
- `/accounts` Account setup and card exposure
- `/settings` Financial profile and recurring commitments

## Environment Variables

Root `.env` for FastAPI:

```text
DATABASE_URL=postgresql+psycopg://spendlens:spendlens@localhost:5432/spendlens
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Frontend `.env.local`:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

`NEXT_PUBLIC_API_BASE_URL` must be the browser-facing FastAPI base URL. In Docker Compose it is set to `http://localhost:8000`, not `http://api:8000`, because browser requests resolve from the host.

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

Credit cards cannot be transfer source accounts in this phase. Credit-card cash advances and balance transfers are not modeled.

Investments reduce liquid cash and count toward the monthly savings target. Credit cards cannot be used as the source account for investment transactions.

Transfers between bank, cash, and wallet accounts move money but do not count as spending.

When a transaction links to a recurring commitment, it must match the commitment's configured account, category, and commitment type. Fixed-expense commitments can only link to expense transactions; investment commitments can only link to investment transactions.

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
- `PUT /api/v1/financial-profile`
- `GET /api/v1/financial-profile`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/cards/exposure`

`GET /api/v1/transactions` supports optional filters: `account_id`, `transaction_type`, `category_id`, `date_from`, and `date_to`.

Dashboard and card exposure endpoints accept an optional `as_of=YYYY-MM-DD` query parameter for deterministic calculations. If omitted, the API uses the current date.

## Initial Categories

Run `python -m app.seed` from `backend/` to create:

Food, EMI, Subscription, Shopping, Travel, Recharge, Investment, Gift, Miscellaneous, Salary.

## Tests and Validation

Backend:

```bash
python -m pytest backend/tests -v
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```
