"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { CategorySetupWarning } from "@/components/ui/SetupWarning";
import {
  createTransaction,
  getAccounts,
  getCategories,
  getCommitments,
  getErrorMessage,
  getTransactions,
} from "@/lib/api";
import { formatDateTime, localDateTimeInputToUtcIso, maxDateTimeLocalNow } from "@/lib/dates";
import { formatMoney, isValidMoneyInput, transactionAmountDisplay } from "@/lib/money";
import type {
  Account,
  Category,
  Commitment,
  CommitmentType,
  Transaction,
  TransactionCreatePayload,
  TransactionFilters,
  TransactionType,
} from "@/lib/types";

interface TransactionFormState {
  transactionType: TransactionType;
  amount: string;
  sourceAccountId: string;
  destinationAccountId: string;
  categoryId: string;
  recurringCommitmentId: string;
  merchant: string;
  description: string;
  occurredAt: string;
}

interface FilterState {
  accountId: string;
  transactionType: "" | TransactionType;
  categoryId: string;
  dateFrom: string;
  dateTo: string;
}

const transactionTypeLabels: Record<TransactionType, string> = {
  expense: "Expense",
  income: "Income",
  transfer: "Transfer",
  investment: "Investment",
  refund: "Refund",
};

const initialForm: TransactionFormState = {
  transactionType: "expense",
  amount: "",
  sourceAccountId: "",
  destinationAccountId: "",
  categoryId: "",
  recurringCommitmentId: "",
  merchant: "",
  description: "",
  occurredAt: "",
};

const initialFilters: FilterState = {
  accountId: "",
  transactionType: "",
  categoryId: "",
  dateFrom: "",
  dateTo: "",
};

function labelForType(type: TransactionType): string {
  return transactionTypeLabels[type];
}

function accountName(accountsById: Map<string, Account>, accountId: string | null): string {
  if (!accountId) {
    return "Not linked";
  }

  return accountsById.get(accountId)?.name ?? "Unknown account";
}

function categoryName(categoriesById: Map<string, Category>, categoryId: string | null): string {
  if (!categoryId) {
    return "Uncategorized";
  }

  return categoriesById.get(categoryId)?.name ?? "Unknown category";
}

function accountContext(transaction: Transaction, accountsById: Map<string, Account>): string {
  if (transaction.transaction_type === "transfer") {
    return `${accountName(accountsById, transaction.source_account_id)} -> ${accountName(
      accountsById,
      transaction.destination_account_id,
    )}`;
  }

  if (transaction.transaction_type === "expense" || transaction.transaction_type === "investment") {
    return accountName(accountsById, transaction.source_account_id);
  }

  return accountName(accountsById, transaction.destination_account_id);
}

function filtersToQuery(filters: FilterState): TransactionFilters {
  return {
    account_id: filters.accountId || undefined,
    transaction_type: filters.transactionType || undefined,
    category_id: filters.categoryId || undefined,
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
  };
}

function commitmentTypeForTransaction(type: TransactionType): CommitmentType | null {
  if (type === "expense") {
    return "fixed_expense";
  }
  if (type === "investment") {
    return "investment";
  }
  return null;
}

export function TransactionsClient() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [form, setForm] = useState<TransactionFormState>(initialForm);
  const [filters, setFilters] = useState<FilterState>(initialFilters);
  const [lookupsLoading, setLookupsLoading] = useState(true);
  const [transactionsLoading, setTransactionsLoading] = useState(true);
  const [lookupsError, setLookupsError] = useState<string | null>(null);
  const [transactionsError, setTransactionsError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const amountInputRef = useRef<HTMLInputElement>(null);
  const formPanelRef = useRef<HTMLElement>(null);

  const loadLookups = useCallback(async () => {
    setLookupsLoading(true);
    setLookupsError(null);

    try {
      const [loadedAccounts, loadedCategories, loadedCommitments] = await Promise.all([
        getAccounts(),
        getCategories(),
        getCommitments(),
      ]);
      setAccounts(loadedAccounts);
      setCategories(loadedCategories);
      setCommitments(loadedCommitments);
    } catch (error) {
      setLookupsError(getErrorMessage(error));
    } finally {
      setLookupsLoading(false);
    }
  }, []);

  const loadTransactions = useCallback(async () => {
    setTransactionsLoading(true);
    setTransactionsError(null);

    try {
      setTransactions(await getTransactions(filtersToQuery(filters)));
    } catch (error) {
      setTransactionsError(getErrorMessage(error));
    } finally {
      setTransactionsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  useEffect(() => {
    void loadTransactions();
  }, [loadTransactions]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("add") === "transaction") {
      formPanelRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
      amountInputRef.current?.focus();
    }
  }, []);

  const activeAccounts = useMemo(() => accounts.filter((account) => account.is_active), [accounts]);
  const nonCreditAccounts = useMemo(
    () => activeAccounts.filter((account) => account.account_type !== "credit_card"),
    [activeAccounts],
  );
  const sourceOptions = useMemo(() => {
    if (form.transactionType === "transfer" || form.transactionType === "investment") {
      return nonCreditAccounts;
    }
    return activeAccounts;
  }, [activeAccounts, form.transactionType, nonCreditAccounts]);
  const destinationOptions = activeAccounts;

  const accountsById = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts]);
  const categoriesById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);
  const selectedDestinationAccount = form.destinationAccountId ? accountsById.get(form.destinationAccountId) : undefined;

  const compatibleCommitments = useMemo(() => {
    const requiredType = commitmentTypeForTransaction(form.transactionType);
    if (!requiredType || !form.sourceAccountId || !form.categoryId) {
      return [];
    }

    return commitments.filter(
      (commitment) =>
        commitment.is_active &&
        commitment.commitment_type === requiredType &&
        commitment.account_id === form.sourceAccountId &&
        commitment.category_id === form.categoryId,
    );
  }, [commitments, form.categoryId, form.sourceAccountId, form.transactionType]);

  useEffect(() => {
    if (
      form.recurringCommitmentId &&
      !compatibleCommitments.some((commitment) => commitment.id === form.recurringCommitmentId)
    ) {
      setForm((current) => ({ ...current, recurringCommitmentId: "" }));
    }
  }, [compatibleCommitments, form.recurringCommitmentId]);

  function updateForm<K extends keyof TransactionFormState>(key: K, value: TransactionFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setSubmitError(null);
    setSubmitSuccess(null);
  }

  function updateFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function handleTypeChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextType = event.target.value as TransactionType;
    setForm((current) => ({
      ...current,
      transactionType: nextType,
      sourceAccountId: nextType === "income" || nextType === "refund" ? "" : current.sourceAccountId,
      destinationAccountId: nextType === "expense" || nextType === "investment" ? "" : current.destinationAccountId,
      categoryId: nextType === "transfer" || nextType === "income" || nextType === "refund" ? "" : current.categoryId,
      recurringCommitmentId: "",
    }));
    setSubmitError(null);
    setSubmitSuccess(null);
  }

  function validateForm(): string | null {
    if (!isValidMoneyInput(form.amount)) {
      return "Enter a rupee amount like 123 or 123.45.";
    }

    if ((form.transactionType === "expense" || form.transactionType === "investment") && !form.sourceAccountId) {
      return "Choose a source account.";
    }

    if ((form.transactionType === "income" || form.transactionType === "refund") && !form.destinationAccountId) {
      return "Choose a destination account.";
    }

    if (form.transactionType === "transfer" && (!form.sourceAccountId || !form.destinationAccountId)) {
      return "Choose both source and destination accounts.";
    }

    if (form.transactionType === "transfer" && form.sourceAccountId === form.destinationAccountId) {
      return "Transfer source and destination accounts must be different.";
    }

    if ((form.transactionType === "expense" || form.transactionType === "investment") && !form.categoryId) {
      return "Choose a category.";
    }

    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    const validationError = validateForm();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }

    const payload: TransactionCreatePayload = {
      transaction_type: form.transactionType,
      amount: form.amount.trim(),
    };

    if (form.transactionType === "expense" || form.transactionType === "investment") {
      payload.source_account_id = form.sourceAccountId;
      payload.category_id = form.categoryId;
      if (form.recurringCommitmentId) {
        payload.recurring_commitment_id = form.recurringCommitmentId;
      }
    }

    if (form.transactionType === "income" || form.transactionType === "refund") {
      payload.destination_account_id = form.destinationAccountId;
    }

    if (form.transactionType === "transfer") {
      payload.source_account_id = form.sourceAccountId;
      payload.destination_account_id = form.destinationAccountId;
    }

    if (form.merchant.trim()) {
      payload.merchant = form.merchant.trim();
    }
    if (form.description.trim()) {
      payload.description = form.description.trim();
    }
    try {
      const occurredAtIso = localDateTimeInputToUtcIso(form.occurredAt);
      if (occurredAtIso) {
        payload.occurred_at = occurredAtIso;
      }
    } catch (dateError) {
      setSubmitError(dateError instanceof Error ? dateError.message : "Enter a valid occurred-at date and time.");
      return;
    }

    setSubmitting(true);
    try {
      await createTransaction(payload);
      setSubmitSuccess("Transaction recorded.");
      setForm((current) => ({
        ...current,
        amount: "",
        merchant: "",
        description: "",
        occurredAt: "",
        recurringCommitmentId: "",
      }));
      await loadTransactions();
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  const showSource = form.transactionType === "expense" || form.transactionType === "transfer" || form.transactionType === "investment";
  const showDestination = form.transactionType === "income" || form.transactionType === "transfer" || form.transactionType === "refund";
  const showCategory = form.transactionType === "expense" || form.transactionType === "investment";
  const showCommitment = showCategory;
  const isCreditCardPayment = form.transactionType === "transfer" && selectedDestinationAccount?.account_type === "credit_card";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Manual entry</p>
          <h1>Transactions</h1>
          <p>Record expenses, income, transfers, investments, and refunds against the existing SpendLens backend.</p>
        </div>
      </header>

      {categories.length === 0 && !lookupsLoading ? <CategorySetupWarning /> : null}

      <section className="panel form-panel" ref={formPanelRef}>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Add transaction</p>
            <h2>Record activity</h2>
          </div>
        </div>

        {lookupsLoading ? <LoadingState label="Loading accounts and categories" rows={2} /> : null}
        {lookupsError ? <ErrorState message={lookupsError} onRetry={loadLookups} /> : null}

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            Transaction type
            <select value={form.transactionType} onChange={handleTypeChange}>
              {(Object.keys(transactionTypeLabels) as TransactionType[]).map((type) => (
                <option key={type} value={type}>
                  {transactionTypeLabels[type]}
                </option>
              ))}
            </select>
          </label>

          <label>
            Amount
            <input
              ref={amountInputRef}
              inputMode="decimal"
              placeholder="123.45"
              value={form.amount}
              onChange={(event) => updateForm("amount", event.target.value)}
              required
            />
          </label>

          {showSource ? (
            <label>
              Source account
              <select
                value={form.sourceAccountId}
                onChange={(event) => updateForm("sourceAccountId", event.target.value)}
                required
              >
                <option value="">Choose source</option>
                {sourceOptions.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name} ({account.account_type.replace("_", " ")})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {showDestination ? (
            <label>
              Destination account
              <select
                value={form.destinationAccountId}
                onChange={(event) => updateForm("destinationAccountId", event.target.value)}
                required
              >
                <option value="">Choose destination</option>
                {destinationOptions.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name} ({account.account_type.replace("_", " ")})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {showCategory ? (
            <label>
              Category
              <select value={form.categoryId} onChange={(event) => updateForm("categoryId", event.target.value)} required>
                <option value="">Choose category</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {showCommitment ? (
            <label>
              Recurring commitment
              <select
                value={form.recurringCommitmentId}
                onChange={(event) => updateForm("recurringCommitmentId", event.target.value)}
              >
                <option value="">No linked commitment</option>
                {compatibleCommitments.map((commitment) => (
                  <option key={commitment.id} value={commitment.id}>
                    {commitment.name} ({formatMoney(commitment.amount)})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <label>
            Merchant
            <input
              maxLength={120}
              placeholder="Optional"
              value={form.merchant}
              onChange={(event) => updateForm("merchant", event.target.value)}
            />
          </label>

          <label className="form-wide">
            Description
            <textarea
              maxLength={500}
              placeholder="Optional note"
              value={form.description}
              onChange={(event) => updateForm("description", event.target.value)}
            />
          </label>

          <label>
            Occurred at
            <input
              type="datetime-local"
              max={maxDateTimeLocalNow()}
              value={form.occurredAt}
              onChange={(event) => updateForm("occurredAt", event.target.value)}
            />
          </label>

          {isCreditCardPayment ? (
            <p className="helper-text form-wide">This will be recorded as a credit-card payment, not another expense.</p>
          ) : null}

          {submitError ? <p className="form-message error form-wide">{submitError}</p> : null}
          {submitSuccess ? <p className="form-message success form-wide">{submitSuccess}</p> : null}

          <div className="form-actions form-wide">
            <button className="primary-button" type="submit" disabled={submitting || lookupsLoading || Boolean(lookupsError)}>
              {submitting ? "Recording..." : "Record Transaction"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel filters-panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Filters</p>
            <h2>Transaction history</h2>
          </div>
          <button className="secondary-button" type="button" onClick={() => setFilters(initialFilters)}>
            Clear Filters
          </button>
        </div>

        <div className="filter-grid">
          <label>
            Account
            <select value={filters.accountId} onChange={(event) => updateFilter("accountId", event.target.value)}>
              <option value="">All accounts</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Type
            <select
              value={filters.transactionType}
              onChange={(event) => updateFilter("transactionType", event.target.value as FilterState["transactionType"])}
            >
              <option value="">All types</option>
              {(Object.keys(transactionTypeLabels) as TransactionType[]).map((type) => (
                <option key={type} value={type}>
                  {transactionTypeLabels[type]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Category
            <select value={filters.categoryId} onChange={(event) => updateFilter("categoryId", event.target.value)}>
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date from
            <input type="date" value={filters.dateFrom} onChange={(event) => updateFilter("dateFrom", event.target.value)} />
          </label>
          <label>
            Date to
            <input type="date" value={filters.dateTo} onChange={(event) => updateFilter("dateTo", event.target.value)} />
          </label>
        </div>

        {transactionsLoading ? <LoadingState label="Loading transactions" rows={4} /> : null}
        {transactionsError ? <ErrorState message={transactionsError} onRetry={loadTransactions} /> : null}
        {!transactionsLoading && !transactionsError && transactions.length === 0 ? (
          <EmptyState
            title="No transactions yet"
            message="Record your first expense, income, transfer, investment, or refund."
            actionHref="/transactions?add=transaction"
            actionLabel="Add transaction"
          />
        ) : null}
        {!transactionsLoading && !transactionsError && transactions.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date/time</th>
                  <th>Merchant</th>
                  <th>Type</th>
                  <th>Category</th>
                  <th>Account context</th>
                  <th className="numeric-cell">Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const amount = transactionAmountDisplay(transaction.transaction_type, transaction.amount);
                  return (
                    <tr key={transaction.id}>
                      <td>{formatDateTime(transaction.occurred_at)}</td>
                      <td>{transaction.merchant?.trim() || labelForType(transaction.transaction_type)}</td>
                      <td>{labelForType(transaction.transaction_type)}</td>
                      <td>{categoryName(categoriesById, transaction.category_id)}</td>
                      <td>{accountContext(transaction, accountsById)}</td>
                      <td className={`numeric-cell amount ${amount.tone}`}>{amount.label}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
