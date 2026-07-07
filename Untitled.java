You are implementing Phase 1 of a personal finance application named SpendLens.

The repository is new. Build the backend foundation and complete the bounded MVP described below.

Do not implement a frontend.

Do not implement AI features.

Do not implement Gmail, SMS, bank API, PDF, or CSV ingestion.

Do not add authentication yet.

The application is currently single-user and for personal use.

## Product Problem

SpendLens is designed for a user who uses credit cards, bank accounts, and UPI for most spending and loses track of how much money is actually safe to spend.

The application's core financial metric is:

safe_to_spend =
liquid_cash

* credit_card_liability
* remaining_fixed_commitments
* remaining_savings_target

Future expected salary must NOT be included in safe_to_spend until it is recorded as an actual income transaction.

The calculation should therefore be conservative.

## Required Stack

Backend:

* Python
* FastAPI
* SQLAlchemy 2.x ORM style
* Pydantic v2
* PostgreSQL
* Alembic
* pytest

Infrastructure:

* Docker
* Docker Compose

Use synchronous SQLAlchemy for this MVP.

Use Decimal for monetary calculations.

Do not use Python floats for persisted or calculated money values.

Use PostgreSQL NUMERIC columns for monetary fields.

## Required Project Structure

Create a clean application structure approximately matching:

backend/
app/
api/
router.py
routes/
accounts.py
categories.py
transactions.py
commitments.py
dashboard.py
core/
config.py
database.py
models/
base.py
account.py
category.py
transaction.py
commitment.py
financial_profile.py
schemas/
account.py
category.py
transaction.py
commitment.py
dashboard.py
services/
balance_service.py
card_service.py
safe_to_spend_service.py
main.py
alembic/
tests/
alembic.ini
requirements.txt
Dockerfile

Also create:

docker-compose.yml
.env.example
README.md

Small structural adjustments are acceptable when they clearly improve maintainability.

Do not introduce repositories, unit-of-work abstractions, event buses, CQRS, or other enterprise abstractions.

Keep the architecture appropriate for a personal MVP.

## Database Models

Use UUID primary keys.

Add created_at and updated_at timestamps where appropriate.

### Account

Fields:

* id
* name
* account_type
* opening_balance
* opening_outstanding
* credit_limit
* billing_day
* due_day
* is_active
* created_at
* updated_at

Supported account types:

* bank
* cash
* wallet
* credit_card

Rules:

For bank, cash, and wallet accounts:

* opening_balance is used
* opening_outstanding must be zero
* credit_limit, billing_day, and due_day must be null

For credit_card accounts:

* opening_outstanding represents existing card liability when tracking begins
* opening_balance must be zero
* credit_limit is required and greater than zero
* billing_day is required and must be between 1 and 28
* due_day is required and must be between 1 and 28

Use validation at the API/schema boundary.

Do not persist a mutable current_balance field.

Balances must be derived from the transaction ledger.

### Category

Fields:

* id
* name
* is_active
* created_at

Category names must be unique.

Seed or document creation of these initial categories:

* Food
* EMI
* Subscription
* Shopping
* Travel
* Recharge
* Investment
* Gift
* Miscellaneous
* Salary

Do not silently create categories when a transaction is submitted with an unknown category.

### Transaction

Fields:

* id
* transaction_type
* amount
* source_account_id
* destination_account_id
* category_id
* recurring_commitment_id
* merchant
* description
* occurred_at
* created_at

Supported transaction types:

* expense
* income
* transfer
* investment
* refund

Amount must always be greater than zero.

Do not use signed transaction amounts.

Validation rules:

expense:

* source_account_id required
* destination_account_id must be null
* category_id required

investment:

* source_account_id required
* destination_account_id must be null
* category_id required
* credit cards cannot be used as the source account for an investment

income:

* destination_account_id required
* source_account_id must be null

refund:

* destination_account_id required
* source_account_id must be null

transfer:

* source_account_id required
* destination_account_id required
* source and destination accounts must be different
* category_id should be null

A credit-card bill payment must be represented as:

transaction_type = transfer
source_account = bank account
destination_account = credit card

It must NOT be counted as an expense.

A credit-card purchase must be represented as:

transaction_type = expense
source_account = credit card

It is counted as spending immediately.

Do not implement double-entry accounting in this phase.

### RecurringCommitment

Fields:

* id
* name
* amount
* category_id
* account_id
* commitment_type
* due_day
* is_active
* created_at
* updated_at

Supported commitment types:

* fixed_expense
* investment

For Phase 1, all recurring commitments are monthly.

due_day must be between 1 and 28.

Transactions may optionally reference recurring_commitment_id.

A commitment is considered fulfilled for the current calendar month when a transaction in that month references its recurring_commitment_id.

Remaining fixed commitments are active fixed_expense commitments that have not been fulfilled during the current calendar month.

Remaining investment commitments must not be included in fixed_commitments.

Savings are handled separately through the savings target.

### FinancialProfile

This is a single-user MVP.

Create a FinancialProfile model with:

* id
* monthly_savings_target
* salary_day
* created_at
* updated_at

salary_day must be between 1 and 28.

The system should tolerate no financial profile existing yet.

Do not hardcode salary or savings values.

## Balance Calculation Rules

Implement BalanceService.

For bank, cash, and wallet accounts:

current_balance =
opening_balance

* income received into account
* refunds received into account
* transfers received

- expenses paid from account
- investments paid from account
- transfers sent

For credit-card accounts:

raw_outstanding =
opening_outstanding

* expenses charged to card

- refunds received into card
- transfers received by card

A bank-to-credit-card transfer therefore reduces card liability.

Expose card liability as max(raw_outstanding, 0).

Do not count credit card liability as liquid cash.

Liquid cash is the sum of positive current balances for active:

* bank
* cash
* wallet

accounts.

Document how an overpaid credit card is handled.

For the MVP, it is acceptable for raw_outstanding to be negative internally while card liability returned by financial exposure calculations is clamped to zero.

## Credit Card Service

Implement CardService.

For every active credit card return:

* account_id
* account_name
* credit_limit
* outstanding
* available_credit
* utilization_percentage
* current_cycle_spend
* billing_day
* due_day

available_credit =
credit_limit - max(outstanding, 0)

utilization_percentage =
max(outstanding, 0) / credit_limit * 100

current_cycle_spend must include expense transactions charged to the card during the current billing cycle.

Interpret billing_day as the statement closing day.

If today is after the billing day:

current cycle starts on billing_day + 1 of the current month.

If today is on or before the billing day:

current cycle starts on billing_day + 1 of the previous month.

The cycle ends on the billing day following the cycle start.

Handle month and year boundaries correctly.

Use testable date logic.

Do not scatter date.today() calls throughout business logic.

Allow the service calculation date to be supplied as an argument, with the current date used only as the API default.

## Safe To Spend Service

Implement SafeToSpendService.

Return:

* liquid_cash
* credit_card_liability
* remaining_fixed_commitments
* monthly_savings_target
* savings_completed_this_month
* remaining_savings_target
* safe_to_spend
* status

Calculate:

remaining_savings_target =
max(
monthly_savings_target - investment_transactions_this_month,
0
)

Only transaction_type = investment counts toward the monthly savings target.

Calculate:

safe_to_spend =
liquid_cash

* credit_card_liability
* remaining_fixed_commitments
* remaining_savings_target

Status rules:

safe_to_spend < 0:

* overcommitted

safe_to_spend == 0:

* fully_allocated

safe_to_spend > 0:

* available

Use Decimal calculations throughout.

If no FinancialProfile exists:

* monthly_savings_target should default to zero for the calculation
* clearly document this behavior

## Required API Endpoints

Use an `/api/v1` prefix.

### Health

GET /health

Return a simple health response.

### Accounts

POST /api/v1/accounts
GET /api/v1/accounts
GET /api/v1/accounts/{account_id}

Implement account creation and reads only.

Do not implement delete yet.

### Categories

POST /api/v1/categories
GET /api/v1/categories

### Transactions

POST /api/v1/transactions
GET /api/v1/transactions

GET should support optional filters:

* account_id
* transaction_type
* category_id
* date_from
* date_to

Use reasonable validation.

### Commitments

POST /api/v1/commitments
GET /api/v1/commitments

### Financial Profile

PUT /api/v1/financial-profile
GET /api/v1/financial-profile

PUT should create or update the single financial profile.

Do not depend on a hardcoded database ID.

### Dashboard

GET /api/v1/dashboard/summary

Return the SafeToSpendService result.

GET /api/v1/cards/exposure

Return active credit-card exposure information.

## Pydantic Schemas

Keep SQLAlchemy ORM models and API schemas separate.

Use Pydantic v2 patterns.

Response schemas backed by ORM objects should support attribute-based validation.

Do not return raw SQLAlchemy models without explicit response schemas.

Create separate create and response schemas where appropriate.

## Database Session

Create a FastAPI database dependency that creates a SQLAlchemy Session for the request and guarantees cleanup after the request finishes.

Do not use one global Session instance.

## Alembic

Initialize and configure Alembic.

Wire Alembic target_metadata to the application's SQLAlchemy Base metadata.

Create an initial migration containing all required Phase 1 tables.

Do not rely on Base.metadata.create_all() during normal application startup.

The application should use migrations as the schema management mechanism.

## Docker

Create a docker-compose.yml with:

* api
* db

The db service must use PostgreSQL.

Use an environment variable for DATABASE_URL.

Add a PostgreSQL health check.

The API should wait for or otherwise correctly handle database startup.

Expose the FastAPI service locally.

Do not add the frontend service yet.

## Tests

Add meaningful pytest tests.

At minimum test:

1. Bank balance calculation.

2. Credit card purchase increases card outstanding.

3. Credit card bill payment does not count as an expense and reduces outstanding.

4. Credit card refund reduces outstanding.

5. Transfer between two bank accounts does not count as spending.

6. Investment reduces liquid cash.

7. Investment contributes to monthly savings target completion.

8. Remaining fixed commitment excludes a commitment fulfilled by a linked transaction in the current month.

9. Unfulfilled active fixed commitment is reserved by safe_to_spend.

10. Future salary is not included in safe_to_spend.

11. Credit card current billing cycle date logic when today is before the billing day.

12. Credit card current billing cycle date logic when today is after the billing day.

13. Billing cycle logic across December to January.

14. Credit card utilization calculation.

15. Negative safe_to_spend returns overcommitted.

16. Zero safe_to_spend returns fully_allocated.

Focus service tests on financial correctness.

Use deterministic dates in tests.

Do not make tests depend on the real current date.

## Seed Data

Provide a simple seed mechanism or documented command to create the initial categories.

Do not automatically create duplicate categories on every application startup.

## README

Write a concise README covering:

* Product problem
* Core financial rule
* Architecture
* Local setup
* Docker setup
* Alembic migration commands
* Running tests
* API endpoints
* Transaction semantics

Explicitly explain:

Credit card purchase = expense immediately.

Credit card bill payment = transfer, not another expense.

This prevents double-counting.

Also document the safe_to_spend formula.

## Engineering Constraints

Do not overengineer.

Do not implement generic plugin systems.

Do not implement a repository pattern solely for abstraction.

Do not add Redis.

Do not add Celery.

Do not add Kafka.

Do not add authentication.

Do not add a frontend.

Do not add AI.

Do not add statement ingestion.

Do not invent future features.

Use type hints.

Keep business calculations in services rather than route handlers.

Keep route handlers thin.

Use clear domain names.

Use Decimal for money.

Use testable date handling.

Avoid circular imports.

Handle expected validation and missing-resource errors with appropriate HTTP responses.

## Execution Instructions

First inspect the repository state.

Then briefly state the implementation plan.

Implement the full bounded Phase 1 backend described above.

Run tests.

Run any available syntax or import checks.

Review the generated Alembic migration.

Fix failures caused by your changes.

Do not stop after scaffolding.

Do not merely provide code snippets or an implementation guide.

Make the changes directly in the repository.

At the end, report:

1. Files created or changed.
2. Database models implemented.
3. API endpoints implemented.
4. Financial calculation rules implemented.
5. Tests added and their result.
6. Commands required to run the project.
7. Any assumptions or limitations.

Do not start Phase 2.
