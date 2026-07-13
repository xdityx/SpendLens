from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionType
from app.services.date_utils import app_date_end_exclusive_utc_naive


ZERO = Decimal("0")


class BalanceService:
    def __init__(self, db: Session):
        self.db = db

    def current_balance(self, account: Account, as_of: date | None = None) -> Decimal:
        if account.account_type == AccountType.CREDIT_CARD:
            return self.raw_credit_card_outstanding(account, as_of)

        inflows = self._sum_transactions(
            Transaction.destination_account_id == account.id,
            Transaction.transaction_type.in_(
                [TransactionType.INCOME, TransactionType.REFUND, TransactionType.TRANSFER]
            ),
            as_of=as_of,
        )
        outflows = self._sum_transactions(
            Transaction.source_account_id == account.id,
            Transaction.transaction_type.in_(
                [TransactionType.EXPENSE, TransactionType.INVESTMENT, TransactionType.TRANSFER]
            ),
            as_of=as_of,
        )
        return Decimal(account.opening_balance) + inflows - outflows

    def raw_credit_card_outstanding(self, account: Account, as_of: date | None = None) -> Decimal:
        expenses = self._sum_transactions(
            Transaction.source_account_id == account.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            as_of=as_of,
        )
        refunds = self._sum_transactions(
            Transaction.destination_account_id == account.id,
            Transaction.transaction_type == TransactionType.REFUND,
            as_of=as_of,
        )
        bill_payments = self._sum_transactions(
            Transaction.destination_account_id == account.id,
            Transaction.transaction_type == TransactionType.TRANSFER,
            as_of=as_of,
        )
        return Decimal(account.opening_outstanding) + expenses - refunds - bill_payments

    def credit_card_liability(self, account: Account, as_of: date | None = None) -> Decimal:
        return max(self.raw_credit_card_outstanding(account, as_of), ZERO)

    def total_credit_card_liability(self, as_of: date | None = None) -> Decimal:
        cards = self.db.scalars(
            select(Account).where(Account.account_type == AccountType.CREDIT_CARD, Account.is_active.is_(True))
        ).all()
        return sum((self.credit_card_liability(card, as_of) for card in cards), ZERO)

    def liquid_cash(self, as_of: date | None = None) -> Decimal:
        accounts = self.db.scalars(
            select(Account).where(
                Account.account_type.in_([AccountType.BANK, AccountType.CASH, AccountType.WALLET]),
                Account.is_active.is_(True),
            )
        ).all()
        balances = (self.current_balance(account, as_of) for account in accounts)
        return sum((balance for balance in balances if balance > ZERO), ZERO)

    def _sum_transactions(self, *criteria: object, as_of: date | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.voided_at.is_(None), *criteria)
        if as_of is not None:
            statement = statement.where(Transaction.occurred_at < app_date_end_exclusive_utc_naive(as_of))
        result = self.db.scalar(statement)
        return Decimal(result or ZERO)
