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
  getDashboardSummary,
  getErrorMessage,
  getFinancialProfile,
  getTransactions,
} from "@/lib/api";
import { formatDateTime } from "@/lib/dates";
import { clampPercentage, formatMoney, moneyToNumber, transactionAmountDisplay } from "@/lib/money";
import type {
  Account,
  Category,
  CreditCardExposure,
  DashboardSummary,
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

function statusClass(status: string): string {
  if (status === "overcommitted") {
    return "status-pill danger";
  }
  if (status === "fully_allocated") {
    return "status-pill warning";
  }
  return "status-pill success";
}

function SummaryCard({ label, value, tone }: { label: string; value: MoneyValue; tone?: "negative" | "positive" }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong className={tone ? `amount ${tone}` : "amount"}>{formatMoney(value)}</strong>
    </article>
  );
}

function RecentTransactionRow({ transaction }: { transaction: Transaction }) {
  const amount = transactionAmountDisplay(transaction.transaction_type, transaction.amount);
  const label = transaction.merchant?.trim() || transactionTypeLabels[transaction.transaction_type];

  return (
    <li className="transaction-row">
      <div>
        <strong>{label}</strong>
        <span>
          {transactionTypeLabels[transaction.transaction_type]} - {formatDateTime(transaction.occurred_at)}
        </span>
      </div>
      <strong className={`amount ${amount.tone}`}>{amount.label}</strong>
    </li>
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
      const [summary, cards, transactions, profile, categories, accounts] = await Promise.all([
        getDashboardSummary(),
        getCardExposure(),
        getTransactions(),
        getFinancialProfile(),
        getCategories(),
        getAccounts(),
      ]);

      setData({ summary, cards, transactions, profile, categories, accounts });
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

  return (
    <div className="page-stack">
      <header className="page-header hero-header">
        <div>
          <p className="eyebrow">Safe to spend</p>
          <h1>{formatMoney(summary.safe_to_spend)}</h1>
          <span className={statusClass(summary.status)}>{statusLabels[summary.status] ?? summary.status}</span>
        </div>
        <Link className="primary-button" href="/transactions?add=transaction">
          Add Transaction
        </Link>
      </header>

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
        <SummaryCard label="Fixed Commitments Left" value={summary.remaining_fixed_commitments} />
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
                      <dt>Cycle spend</dt>
                      <dd>{formatMoney(card.current_cycle_spend)}</dd>
                    </div>
                    <div>
                      <dt>Billing / Due</dt>
                      <dd>
                        Day {card.billing_day} / Day {card.due_day}
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
                <RecentTransactionRow key={transaction.id} transaction={transaction} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
