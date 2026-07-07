# SpendLens

SpendLens is a personal finance backend for tracking how much money is actually safe to spend when spending happens across bank accounts, cash, wallets, UPI, and credit cards.

Phase 1 is intentionally backend-only. There is no frontend, authentication, AI, statement ingestion, Gmail/SMS integration, bank API integration, PDF parsing, or CSV import.

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

- Python, FastAPI, Pydantic v2
- SQLAlchemy 2.x synchronous ORM
- PostgreSQL with NUMERIC monetary columns
- Alembic migrations for schema management
- Decimal-based monetary calculations
- Docker Compose for local API + PostgreSQL

Business calculations live in `backend/app/services`. Route handlers stay thin and use explicit Pydantic schemas instead of returning raw SQLAlchemy models.

## Local Setup

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

## Docker Setup

```bash
docker compose up --build
```

The `api` service waits for the PostgreSQL health check, runs Alembic migrations, then starts FastAPI on `http://127.0.0.1:8000`.

Seed initial categories after the service is up:

```bash
docker compose exec api python -m app.seed
```

The seed command is idempotent and does not create duplicate categories.

## Alembic Commands

Run from `backend/`:

```bash
alembic upgrade head
alembic current
alembic revision --autogenerate -m "describe change"
```

Normal application startup does not call `Base.metadata.create_all()`. Schema changes should go through migrations.

## Tests

```bash
python -m pytest backend/tests -v
```

The service tests use deterministic dates and an in-memory database.

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

## Transaction Semantics

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
source_account = bank account
destination_account = credit card
```

This reduces bank cash and reduces card liability. It is not another expense, which prevents double-counting.

Investments reduce liquid cash and count toward the monthly savings target. Credit cards cannot be used as the source account for investment transactions.

Transfers between bank, cash, and wallet accounts move money but do not count as spending.

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

## Initial Categories

Run `python -m app.seed` from `backend/` to create:

Food, EMI, Subscription, Shopping, Travel, Recharge, Investment, Gift, Miscellaneous, Salary.
