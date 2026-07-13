from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import BalanceService
from app.services.card_service import CardService
from app.services.safe_to_spend_service import SafeToSpendService


D = Decimal
AS_OF = date(2026, 7, 7)


def at(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, 0)


def add_category(db: Session, name: str = "Food") -> Category:
    category = Category(name=name)
    db.add(category)
    db.flush()
    return category


def add_bank(db: Session, name: str = "Bank", opening_balance: str = "0") -> Account:
    account = Account(
        name=name,
        account_type=AccountType.BANK,
        opening_balance=D(opening_balance),
        opening_outstanding=D("0"),
    )
    db.add(account)
    db.flush()
    return account


def add_card(
    db: Session,
    name: str = "Card",
    opening_outstanding: str = "0",
    credit_limit: str = "1000",
    billing_day: int = 15,
    due_day: int = 25,
) -> Account:
    account = Account(
        name=name,
        account_type=AccountType.CREDIT_CARD,
        opening_balance=D("0"),
        opening_outstanding=D(opening_outstanding),
        credit_limit=D(credit_limit),
        billing_day=billing_day,
        due_day=due_day,
    )
    db.add(account)
    db.flush()
    return account


def add_transaction(
    db: Session,
    transaction_type: TransactionType,
    amount: str,
    occurred_at: datetime = at(2026, 7, 7),
    source_account: Account | None = None,
    destination_account: Account | None = None,
    category: Category | None = None,
    commitment: RecurringCommitment | None = None,
) -> Transaction:
    transaction = Transaction(
        transaction_type=transaction_type,
        amount=D(amount),
        source_account_id=source_account.id if source_account else None,
        destination_account_id=destination_account.id if destination_account else None,
        category_id=category.id if category else None,
        recurring_commitment_id=commitment.id if commitment else None,
        occurred_at=occurred_at,
    )
    db.add(transaction)
    db.flush()
    return transaction


def add_commitment(
    db: Session,
    account: Account,
    category: Category,
    amount: str,
    commitment_type: CommitmentType = CommitmentType.FIXED_EXPENSE,
) -> RecurringCommitment:
    commitment = RecurringCommitment(
        name="Commitment",
        amount=D(amount),
        category_id=category.id,
        account_id=account.id,
        commitment_type=commitment_type,
        due_day=10,
        is_active=True,
    )
    db.add(commitment)
    db.flush()
    return commitment


def add_profile(db: Session, target: str = "0") -> FinancialProfile:
    profile = FinancialProfile(monthly_savings_target=D(target), salary_day=1)
    db.add(profile)
    db.flush()
    return profile


def test_bank_balance_calculation(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="1000")
    other_bank = add_bank(db_session, name="Other", opening_balance="0")

    add_transaction(db_session, TransactionType.INCOME, "500", destination_account=bank)
    add_transaction(db_session, TransactionType.REFUND, "50", destination_account=bank)
    add_transaction(db_session, TransactionType.EXPENSE, "200", source_account=bank, category=category)
    add_transaction(db_session, TransactionType.INVESTMENT, "100", source_account=bank, category=category)
    add_transaction(db_session, TransactionType.TRANSFER, "150", source_account=bank, destination_account=other_bank)
    add_transaction(db_session, TransactionType.TRANSFER, "75", source_account=other_bank, destination_account=bank)

    assert BalanceService(db_session).current_balance(bank, AS_OF) == D("1175.00")


def test_credit_card_purchase_increases_card_outstanding(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, opening_outstanding="100")

    add_transaction(db_session, TransactionType.EXPENSE, "250", source_account=card, category=category)

    assert BalanceService(db_session).credit_card_liability(card, AS_OF) == D("350.00")


def test_credit_card_bill_payment_is_transfer_and_reduces_outstanding(db_session: Session) -> None:
    bank = add_bank(db_session, opening_balance="1000")
    card = add_card(db_session, opening_outstanding="500")

    add_transaction(db_session, TransactionType.TRANSFER, "300", source_account=bank, destination_account=card)

    service = BalanceService(db_session)
    assert service.current_balance(bank, AS_OF) == D("700.00")
    assert service.credit_card_liability(card, AS_OF) == D("200.00")


def test_credit_card_refund_reduces_outstanding(db_session: Session) -> None:
    card = add_card(db_session, opening_outstanding="500")

    add_transaction(db_session, TransactionType.REFUND, "120", destination_account=card)

    assert BalanceService(db_session).credit_card_liability(card, AS_OF) == D("380.00")


def test_transfer_between_bank_accounts_does_not_count_as_spending(db_session: Session) -> None:
    first = add_bank(db_session, name="First", opening_balance="1000")
    second = add_bank(db_session, name="Second", opening_balance="200")

    add_transaction(db_session, TransactionType.TRANSFER, "300", source_account=first, destination_account=second)

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["liquid_cash"] == D("1200.00")
    assert summary["safe_to_spend"] == D("1200.00")


def test_investment_reduces_liquid_cash(db_session: Session) -> None:
    category = add_category(db_session, "Investment")
    bank = add_bank(db_session, opening_balance="1000")

    add_transaction(db_session, TransactionType.INVESTMENT, "200", source_account=bank, category=category)

    assert BalanceService(db_session).liquid_cash(AS_OF) == D("800.00")


def test_investment_contributes_to_monthly_savings_target(db_session: Session) -> None:
    category = add_category(db_session, "Investment")
    bank = add_bank(db_session, opening_balance="1000")
    add_profile(db_session, target="500")

    add_transaction(db_session, TransactionType.INVESTMENT, "200", source_account=bank, category=category)

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["savings_completed_this_month"] == D("200.00")
    assert summary["remaining_savings_target"] == D("300.00")
    assert summary["safe_to_spend"] == D("500.00")


def test_fulfilled_fixed_commitment_is_excluded_from_remaining_commitments(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="1000")
    commitment = add_commitment(db_session, bank, category, "300")

    add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "300",
        source_account=bank,
        category=category,
        commitment=commitment,
    )

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["remaining_fixed_commitments"] == D("0")


def test_unfulfilled_fixed_commitment_is_reserved_by_safe_to_spend(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="1000")
    add_commitment(db_session, bank, category, "300")

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["remaining_fixed_commitments"] == D("300.00")
    assert summary["safe_to_spend"] == D("700.00")


def test_future_salary_transaction_is_not_included_in_safe_to_spend(db_session: Session) -> None:
    salary = add_category(db_session, "Salary")
    bank = add_bank(db_session, opening_balance="100")
    add_profile(db_session, target="0")

    add_transaction(
        db_session,
        TransactionType.INCOME,
        "1000",
        occurred_at=at(2026, 7, 20),
        destination_account=bank,
        category=salary,
    )

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["liquid_cash"] == D("100.00")
    assert summary["safe_to_spend"] == D("100.00")


def test_card_cycle_before_reset_day_uses_previous_reset(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, billing_day=15)

    add_transaction(db_session, TransactionType.EXPENSE, "25", occurred_at=at(2026, 6, 14), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "100", occurred_at=at(2026, 6, 15), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "200", occurred_at=at(2026, 6, 16), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "50", occurred_at=at(2026, 7, 10), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "70", occurred_at=at(2026, 7, 11), source_account=card, category=category)

    exposure = CardService(db_session).credit_card_exposure(card, date(2026, 7, 10))
    assert exposure["current_cycle_spend"] == D("350.00")
    assert exposure["cycle_start_date"] == date(2026, 6, 15)
    assert exposure["cycle_end_date"] == date(2026, 7, 14)


def test_card_cycle_after_reset_day_starts_on_reset_day(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, billing_day=15)

    add_transaction(db_session, TransactionType.EXPENSE, "25", occurred_at=at(2026, 7, 14), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "100", occurred_at=at(2026, 7, 15), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "200", occurred_at=at(2026, 7, 16), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "50", occurred_at=at(2026, 7, 20), source_account=card, category=category)

    exposure = CardService(db_session).credit_card_exposure(card, date(2026, 7, 20))
    assert exposure["current_cycle_spend"] == D("350.00")
    assert exposure["cycle_start_date"] == date(2026, 7, 15)
    assert exposure["cycle_end_date"] == date(2026, 8, 14)


def test_card_cycle_resets_on_the_configured_day(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, billing_day=15)

    add_transaction(db_session, TransactionType.EXPENSE, "100", occurred_at=at(2026, 7, 14), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "200", occurred_at=at(2026, 7, 15), source_account=card, category=category)

    assert CardService(db_session).current_cycle_spend(card, date(2026, 7, 15)) == D("200.00")


def test_card_cycle_across_december_to_january(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, billing_day=15)

    add_transaction(db_session, TransactionType.EXPENSE, "25", occurred_at=at(2025, 12, 14), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "100", occurred_at=at(2025, 12, 15), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "200", occurred_at=at(2025, 12, 16), source_account=card, category=category)
    add_transaction(db_session, TransactionType.EXPENSE, "50", occurred_at=at(2026, 1, 10), source_account=card, category=category)

    exposure = CardService(db_session).credit_card_exposure(card, date(2026, 1, 10))
    assert exposure["current_cycle_spend"] == D("350.00")
    assert exposure["cycle_start_date"] == date(2025, 12, 15)
    assert exposure["cycle_end_date"] == date(2026, 1, 14)


def test_credit_card_utilization_calculation(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, opening_outstanding="100", credit_limit="1000")
    add_transaction(db_session, TransactionType.EXPENSE, "150", source_account=card, category=category)

    exposure = CardService(db_session).credit_card_exposure(card, AS_OF)
    assert exposure["outstanding"] == D("250.00")
    assert exposure["available_credit"] == D("750.00")
    assert exposure["utilization_percentage"] == D("25.00")


def test_negative_safe_to_spend_returns_overcommitted(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="100")
    add_commitment(db_session, bank, category, "200")

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["safe_to_spend"] == D("-100.00")
    assert summary["status"] == "overcommitted"


def test_zero_safe_to_spend_returns_fully_allocated(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="100")
    add_commitment(db_session, bank, category, "100")

    summary = SafeToSpendService(db_session).summary(AS_OF)
    assert summary["safe_to_spend"] == D("0.00")
    assert summary["status"] == "fully_allocated"
