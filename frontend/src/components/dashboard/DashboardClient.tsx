"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { CategorySetupWarning } from "@/components/ui/SetupWarning";
import {
  getAccounts,
  getCardExposure,
  getCategories,
  getCommitments,
  getCommitmentStatuses,
  getDashboardSummary,
  getEmiPlans,
  getErrorMessage,
  getFinancialProfile,
  getTransactions,
} from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/dates";
import { clampPercentage, formatMoney, moneyToNumber, transactionAmountDisplay } from "@/lib/money";
import type {
  Account,
  Category,
  Commitment,
  CommitmentStatus,
  CreditCardExposure,
  DashboardSummary,
  EMIPlan,
  FinancialProfile,
  MoneyValue,
  Transaction,
  TransactionType,
} from "@/lib/types";

interface DashboardData {
  summary: DashboardSummary;
  cards: CreditCardExposure[];
  transactions: Transaction[];
  profile: FinancialProfile | null;
  categories: Category[];
  accounts: Account[];
  commitments: Commitment[];
  commitmentStatuses: CommitmentStatus[];
  emiPlans: EMIPlan[];
}

const statusLabels: Record<string, string> = {
  available: "Available to spend",
  fully_allocated: "Fully allocated",
  overcommitted: "Overcommitted",
};

const transactionTypeLabels: Record<TransactionType, string> = {
  expense: "Expense",
  income: "Income",
  transfer: "Transfer",
  investment: "Investment",
  refund: "Refund",
};

const commitmentStatusLabels: Record<CommitmentStatus["status"], string> = {
  paid: "Paid",
  partial: "Partially paid",
  overdue_partial: "Partially paid - overdue",
  upcoming: "Upcoming",
  due_today: "Due today",
  overdue: "Overdue",
};

function statusClass(status: string): string {
  if (status === "overcommitted") {
    return "status-pill danger";
  }
  if (status === "fully_allocated") {
    return "status-pill warning";
  }
  return "status-pill success";
}

function obligationStatusClass(status: CommitmentStatus["status"]): string {
  if (status === "paid") {
    return "status-pill success";
  }
  if (status === "overdue" || status === "overdue_partial") {
    return "status-pill danger";
  }
  return "status-pill warning";
}

function accountName(accountsById: Map<string, Account>, accountId: string | null): string {
  if (!accountId) {
    return "Not linked";
  }
  return accountsById.get(accountId)?.name ?? "Unknown account";
}

function categoryName(categoriesById: Map<string, Category>, categoryId: string | null, fallback = "Uncategorized"): string {
  if (!categoryId) {
    return fallback;
  }
  return categoriesById.get(categoryId)?.name ?? "Unknown category";
}

function accountContext(transaction: Transaction, accountsById: Map<string, Account>): string {
  if (transaction.transaction_type === "transfer") {
    return `${accountName(accountsById, transaction.source_account_id)} -> ${accountName(accountsById, transaction.destination_account_id)}`;
  }

  if (transaction.transaction_type === "expense" || transaction.transaction_type === "investment") {
    return accountName(accountsById, transaction.source_account_id);
  }

  return accountName(accountsById, transaction.destination_account_id);
}

function SummaryCard({ label, value, tone }: { label: string; value: MoneyValue; tone?: "negative" | "positive" }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong className={tone ? `amount ${tone}` : "amount"}>{formatMoney(value)}</strong>
    </article>
  );
}

function BreakdownRow({ label, value, tone }: { label: string; value: MoneyValue; tone?: "negative" | "positive" }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone ? `amount ${tone}` : "amount"}>{formatMoney(value)}</dd>
    </div>
  );
}

function RecentTransactionRow({
  accountsById,
  categoriesById,
  commitmentsById,
  emiPlansById,
  transaction,
}: {
  accountsById: Map<string, Account>;
  categoriesById: Map<string, Category>;
  commitmentsById: Map<string, Commitment>;
  emiPlansById: Map<string, EMIPlan>;
  transaction: Transaction;
}) {
  const amount = transactionAmountDisplay(transaction.transaction_type, transaction.amount);
  const linkedCommitment = transaction.recurring_commitment_id ? commitmentsById.get(transaction.recurring_commitment_id) : undefined;
  const linkedEmiPlan = transaction.emi_plan_id ? emiPlansById.get(transaction.emi_plan_id) : undefined;
  const label = transaction.merchant?.trim() || linkedCommitment?.name || linkedEmiPlan?.name || transactionTypeLabels[transaction.transaction_type];
  const secondary = [
    categoryName(categoriesById, transaction.category_id, transactionTypeLabels[transaction.transaction_type]),
    accountContext(transaction, accountsById),
    formatDateTime(transaction.occurred_at),
  ].join(" - ");

  return (
    <li className="transaction-row">
      <div>
        <strong>{label}</strong>
        <span>{secondary}</span>
      </div>
      <strong className={`amount ${amount.tone}`}>{amount.label}</strong>
    </li>
  );
}

function CommitmentObligationCard({ status }: { status: CommitmentStatus }) {
  const hasRemaining = moneyToNumber(status.remaining_amount_this_month) > 0;

  return (
    <article className="account-card obligation-card">
      <div className="section-heading-row compact">
        <div>
          <h3>{status.name}</h3>
          <p>Due {formatDate(status.due_date)}</p>
        </div>
        <span className={obligationStatusClass(status.status)}>{commitmentStatusLabels[status.status]}</span>
      </div>
      <dl className="detail-grid">
        <div>
          <dt>Amount</dt>
          <dd>{formatMoney(status.amount)}</dd>
        </div>
        <div>
          <dt>Paid this month</dt>
          <dd>{formatMoney(status.paid_amount_this_month)}</dd>
        </div>
        <div>
          <dt>Remaining this month</dt>
          <dd>{formatMoney(status.remaining_amount_this_month)}</dd>
        </div>
        <div>
          <dt>Due date</dt>
          <dd>{formatDate(status.due_date)}</dd>
        </div>
      </dl>
      {hasRemaining ? (
        <Link className="secondary-button card-action" href={`/transactions?commitment_id=${status.commitment_id}`}>
          Record payment
        </Link>
      ) : null}
    </article>
  );
}

export function DashboardClient() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [summary, cards, transactions, profile, categories, accounts, commitments, commitmentStatuses, emiPlans] = await Promise.all([
        getDashboardSummary(),
        getCardExposure(),
        getTransactions(),
        getFinancialProfile(),
        getCategories(),
        getAccounts(),
        getCommitments(),
        getCommitmentStatuses(),
        getEmiPlans(),
      ]);

      setData({ summary, cards, transactions, profile, categories, accounts, commitments, commitmentStatuses, emiPlans });
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const recentTransactions = useMemo(() => data?.transactions.slice(0, 8) ?? [], [data?.transactions]);
  const accountsById = useMemo(() => new Map(data?.accounts.map((account) => [account.id, account]) ?? []), [data?.accounts]);
  const categoriesById = useMemo(() => new Map(data?.categories.map((category) => [category.id, category]) ?? []), [data?.categories]);
  const commitmentsById = useMemo(() => new Map(data?.commitments.map((commitment) => [commitment.id, commitment]) ?? []), [data?.commitments]);
  const emiPlansById = useMemo(() => new Map(data?.emiPlans.map((plan) => [plan.id, plan]) ?? []), [data?.emiPlans]);

  if (loading) {
    return <LoadingState label="Loading your spending position" rows={5} />;
  }

  if (error || !data) {
    return (
      <ErrorState
        title="SpendLens API is unavailable"
        message={error ?? "SpendLens API is unavailable. Confirm the FastAPI service is running."}
        onRetry={loadDashboard}
      />
    );
  }

  const { summary } = data;
  const savingsTarget = moneyToNumber(summary.monthly_savings_target);
  const savingsCompleted = moneyToNumber(summary.savings_completed_this_month);
  const savingsProgress = savingsTarget > 0 ? Math.min(100, Math.max(0, (savingsCompleted / savingsTarget) * 100)) : 0;
  const isNegativeSafeToSpend = moneyToNumber(summary.safe_to_spend) < 0;
  const isNegativeDueSoon = moneyToNumber(summary.due_soon_cash_position) < 0;

  return (
    <div className="page-stack">
      <div className="dashboard-overview">
        <header className="page-header hero-header">
          <div>
            <p className="eyebrow">Safe to spend</p>
            <h1>{formatMoney(summary.safe_to_spend)}</h1>
            <span className={statusClass(summary.status)}>{statusLabels[summary.status] ?? summary.status}</span>
            <p className="hero-caption">
              Conservative position after all card debt, including unbilled purchases, and this month&apos;s reserved obligations.
            </p>
          </div>
          <Link className="primary-button" href="/transactions?add=transaction">
            Add Transaction
          </Link>
        </header>

        <section className="panel breakdown-panel" aria-label="Safe to Spend breakdown">
          <div className="section-heading-row compact">
            <div>
              <p className="eyebrow">Why this amount?</p>
              <h2>Safe to Spend breakdown</h2>
            </div>
          </div>
          <dl className="breakdown-list">
            <BreakdownRow label="Liquid cash" value={summary.liquid_cash} tone="positive" />
            <BreakdownRow label="Card liability" value={summary.credit_card_liability} tone="negative" />
            <BreakdownRow label="Fixed commitments left" value={summary.remaining_fixed_commitments} />
            <BreakdownRow label="EMI installments left" value={summary.remaining_emi_installments} />
            <BreakdownRow label="Savings target left" value={summary.remaining_savings_target} />
            <BreakdownRow label="Safe to Spend" value={summary.safe_to_spend} tone={isNegativeSafeToSpend ? "negative" : "positive"} />
          </dl>
          <p className="helper-text">
            Card liability contains {formatMoney(summary.statement_balance_due)} currently due and{" "}
            {formatMoney(summary.unbilled_card_liability)} for later statements.
          </p>
          {isNegativeSafeToSpend ? (
            <p className="helper-text">Your current cash does not fully cover recorded liabilities and reserved obligations.</p>
          ) : null}
        </section>
      </div>

      {data.categories.length === 0 ? <CategorySetupWarning /> : null}

      {data.accounts.length === 0 ? (
        <EmptyState
          title="No accounts yet"
          message="Add your first bank account or credit card so SpendLens can calculate your safe-to-spend position."
          actionHref="/accounts"
          actionLabel="Add account"
        />
      ) : null}

      {data.profile === null ? (
        <EmptyState
          title="No financial profile"
          message="Set a monthly savings target and salary day to reserve savings in Safe to Spend."
          actionHref="/settings"
          actionLabel="Open settings"
        />
      ) : null}

      <section className="metric-grid" aria-label="Financial summary">
        <SummaryCard label="Liquid Cash" value={summary.liquid_cash} tone="positive" />
        <SummaryCard label="Card Liability" value={summary.credit_card_liability} tone="negative" />
        <SummaryCard label="Statement Due" value={summary.statement_balance_due} tone="negative" />
        <SummaryCard label="Unbilled Card Spend" value={summary.unbilled_card_liability} />
        <SummaryCard
          label="Due-Soon Cash Position"
          value={summary.due_soon_cash_position}
          tone={isNegativeDueSoon ? "negative" : "positive"}
        />
        <SummaryCard label="Fixed Commitments Left" value={summary.remaining_fixed_commitments} />
        <SummaryCard label="EMI Installments Left" value={summary.remaining_emi_installments} />
        <SummaryCard label="Savings Target Left" value={summary.remaining_savings_target} />
      </section>

      <section className="panel savings-panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Savings progress</p>
            <h2>Savings this month</h2>
          </div>
          {savingsTarget > 0 ? (
            <strong>
              {formatMoney(summary.savings_completed_this_month)} / {formatMoney(summary.monthly_savings_target)}
            </strong>
          ) : null}
        </div>
        {savingsTarget > 0 ? (
          <div
            className="progress-track"
            role="progressbar"
            aria-label="Savings target progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(savingsProgress)}
          >
            <span className="progress-fill" style={{ width: `${savingsProgress}%` }} />
          </div>
        ) : (
          <p>
            No monthly savings target set. <Link href="/settings">Set one in Settings.</Link>
          </p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Monthly obligations</p>
            <h2>Fixed commitments</h2>
          </div>
          <Link href="/settings">Settings</Link>
        </div>
        {data.commitmentStatuses.length === 0 ? (
          <EmptyState title="No fixed commitments" message="Create fixed monthly commitments in Settings to reserve them here." />
        ) : (
          <div className="card-list obligation-grid">
            {data.commitmentStatuses.map((status) => (
              <CommitmentObligationCard key={status.commitment_id} status={status} />
            ))}
          </div>
        )}
      </section>

      <section className="content-grid two-column">
        <div className="panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Credit cards</p>
              <h2>Card exposure</h2>
            </div>
            <Link href="/accounts">Accounts</Link>
          </div>

          {data.cards.length === 0 ? (
            <EmptyState
              title="No credit cards yet"
              message="Add a card to track billing-cycle exposure."
              actionHref="/accounts"
              actionLabel="Add card"
            />
          ) : (
            <div className="card-exposure-list">
              {data.cards.map((card) => (
                <article className="exposure-card" key={card.account_id}>
                  <div className="section-heading-row compact">
                    <h3>{card.account_name}</h3>
                    <strong>{formatMoney(card.outstanding)}</strong>
                  </div>
                  <dl className="detail-grid">
                    <div>
                      <dt>Credit limit</dt>
                      <dd>{formatMoney(card.credit_limit)}</dd>
                    </div>
                    <div>
                      <dt>Available credit</dt>
                      <dd>{formatMoney(card.available_credit)}</dd>
                    </div>
                    <div>
                      <dt>Statement due</dt>
                      <dd>{formatMoney(card.statement_balance_due)}</dd>
                    </div>
                    <div>
                      <dt>Unbilled balance</dt>
                      <dd>{formatMoney(card.unbilled_balance)}</dd>
                    </div>
                    <div>
                      <dt>Statement due date</dt>
                      <dd>{card.statement_due_date ? formatDate(card.statement_due_date) : "Not set"}</dd>
                    </div>
                    <div>
                      <dt>Cycle spend</dt>
                      <dd>{formatMoney(card.current_cycle_spend)}</dd>
                    </div>
                    <div>
                      <dt>Reset / Due day</dt>
                      <dd>
                        Day {card.billing_day} / Day {card.due_day}
                      </dd>
                    </div>
                    <div className="form-wide">
                      <dt>Cycle window</dt>
                      <dd>
                        {formatDate(card.cycle_start_date)} - {formatDate(card.cycle_end_date)}
                      </dd>
                    </div>
                  </dl>
                  <div className="utilization-row">
                    <span>Utilization {card.utilization_percentage}%</span>
                    <div className="progress-track slim" aria-hidden="true">
                      <span className="progress-fill" style={{ width: `${clampPercentage(card.utilization_percentage)}%` }} />
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Activity</p>
              <h2>Recent transactions</h2>
            </div>
            <Link href="/transactions">View all</Link>
          </div>

          {recentTransactions.length === 0 ? (
            <EmptyState
              title="No transactions yet"
              message="Record your first expense, income, transfer, investment, or refund."
              actionHref="/transactions?add=transaction"
              actionLabel="Record transaction"
            />
          ) : (
            <ul className="transaction-list">
              {recentTransactions.map((transaction) => (
                <RecentTransactionRow
                  accountsById={accountsById}
                  categoriesById={categoriesById}
                  commitmentsById={commitmentsById}
                  emiPlansById={emiPlansById}
                  key={transaction.id}
                  transaction={transaction}
                />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
