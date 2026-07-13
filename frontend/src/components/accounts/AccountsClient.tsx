"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { createAccount, getAccounts, getCardExposure, getErrorMessage, updateCardStatement } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { clampPercentage, formatMoney, isValidMoneyInput, isValidNonNegativeMoneyInput, moneyToNumber } from "@/lib/money";
import type { Account, AccountCreatePayload, AccountType, CreditCardExposure } from "@/lib/types";

interface AccountFormState {
  name: string;
  accountType: AccountType;
  openingBalance: string;
  openingOutstanding: string;
  creditLimit: string;
  billingDay: string;
  dueDay: string;
}

const initialForm: AccountFormState = {
  name: "",
  accountType: "bank",
  openingBalance: "",
  openingOutstanding: "0",
  creditLimit: "",
  billingDay: "",
  dueDay: "",
};

const accountTypeLabels: Record<AccountType, string> = {
  bank: "Bank",
  cash: "Cash",
  wallet: "Wallet",
  credit_card: "Credit card",
};

function parseDay(value: string): number | null {
  if (!/^\d+$/.test(value)) {
    return null;
  }

  const parsed = Number(value);
  if (parsed < 1 || parsed > 28) {
    return null;
  }

  return parsed;
}

export function AccountsClient() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cards, setCards] = useState<CreditCardExposure[]>([]);
  const [form, setForm] = useState<AccountFormState>(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [editingStatementId, setEditingStatementId] = useState<string | null>(null);
  const [statementAmount, setStatementAmount] = useState("");
  const [statementDueDate, setStatementDueDate] = useState("");
  const [statementError, setStatementError] = useState<string | null>(null);
  const [statementMessage, setStatementMessage] = useState<string | null>(null);
  const [statementSubmitting, setStatementSubmitting] = useState(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [loadedAccounts, loadedCards] = await Promise.all([getAccounts(), getCardExposure()]);
      setAccounts(loadedAccounts);
      setCards(loadedCards);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const liquidAccounts = useMemo(
    () => accounts.filter((account) => account.account_type === "bank" || account.account_type === "cash" || account.account_type === "wallet"),
    [accounts],
  );
  const creditCardAccounts = useMemo(
    () => accounts.filter((account) => account.account_type === "credit_card"),
    [accounts],
  );
  const cardsByAccountId = useMemo(() => new Map(cards.map((card) => [card.account_id, card])), [cards]);

  function updateForm<K extends keyof AccountFormState>(key: K, value: AccountFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setSubmitError(null);
    setSubmitSuccess(null);
  }

  function validateForm(): string | null {
    if (!form.name.trim()) {
      return "Enter an account name.";
    }

    if (form.accountType === "credit_card") {
      if (form.openingOutstanding.trim() && !isValidNonNegativeMoneyInput(form.openingOutstanding)) {
        return "Enter opening outstanding as a rupee amount.";
      }
      if (!isValidMoneyInput(form.creditLimit)) {
        return "Enter a credit limit like 50000 or 50000.00.";
      }
      if (parseDay(form.billingDay) === null) {
        return "Enter a cycle reset day from 1 to 28.";
      }
      if (parseDay(form.dueDay) === null) {
        return "Enter a due day from 1 to 28.";
      }
      return null;
    }

    if (form.openingBalance.trim() && !isValidNonNegativeMoneyInput(form.openingBalance)) {
      return "Enter opening balance as a rupee amount.";
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

    const isCreditCard = form.accountType === "credit_card";
    const billingDay = parseDay(form.billingDay);
    const dueDay = parseDay(form.dueDay);
    const payload: AccountCreatePayload = {
      name: form.name.trim(),
      account_type: form.accountType,
      opening_balance: isCreditCard ? "0" : form.openingBalance.trim() || "0",
      opening_outstanding: isCreditCard ? form.openingOutstanding.trim() || "0" : "0",
      is_active: true,
    };

    if (isCreditCard) {
      payload.credit_limit = form.creditLimit.trim();
      payload.billing_day = billingDay;
      payload.due_day = dueDay;
    }

    setSubmitting(true);
    try {
      await createAccount(payload);
      setSubmitSuccess("Account created.");
      setForm(initialForm);
      await loadAccounts();
    } catch (submitErrorValue) {
      setSubmitError(getErrorMessage(submitErrorValue));
    } finally {
      setSubmitting(false);
    }
  }

  function startStatementEdit(account: Account, exposure: CreditCardExposure | undefined) {
    setEditingStatementId(account.id);
    setStatementAmount(String(exposure?.statement_balance_due ?? account.statement_balance ?? "0"));
    setStatementDueDate(exposure?.statement_due_date ?? account.statement_due_date ?? "");
    setStatementError(null);
    setStatementMessage(null);
  }

  function cancelStatementEdit() {
    setEditingStatementId(null);
    setStatementAmount("");
    setStatementDueDate("");
    setStatementError(null);
  }

  async function handleStatementSubmit(
    event: FormEvent<HTMLFormElement>,
    account: Account,
    exposure: CreditCardExposure | undefined,
  ) {
    event.preventDefault();
    setStatementError(null);
    setStatementMessage(null);

    const amount = statementAmount.trim() || "0";
    if (!isValidNonNegativeMoneyInput(amount)) {
      setStatementError("Enter the current statement amount as a rupee value.");
      return;
    }

    const amountValue = moneyToNumber(amount);
    if (amountValue > 0 && !statementDueDate) {
      setStatementError("Choose the date this statement is due.");
      return;
    }
    if (exposure && amountValue > moneyToNumber(exposure.outstanding)) {
      setStatementError("Statement due cannot exceed the card's total outstanding.");
      return;
    }

    setStatementSubmitting(true);
    try {
      await updateCardStatement(account.id, {
        statement_balance: amount,
        statement_due_date: amountValue > 0 ? statementDueDate : null,
      });
      setStatementMessage(amountValue > 0 ? "Statement balance updated." : "Statement balance cleared.");
      setEditingStatementId(null);
      setStatementAmount("");
      setStatementDueDate("");
      await loadAccounts();
    } catch (updateError) {
      setStatementError(getErrorMessage(updateError));
    } finally {
      setStatementSubmitting(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading accounts" rows={4} />;
  }

  if (error) {
    return <ErrorState title="Unable to load accounts" message={error} onRetry={loadAccounts} />;
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Setup</p>
          <h1>Accounts</h1>
          <p>Add bank, cash, wallet, and credit-card accounts. SpendLens uses backend calculations for financial exposure.</p>
        </div>
      </header>

      <section className="panel form-panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Add account</p>
            <h2>Create account</h2>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            Account type
            <select
              value={form.accountType}
              onChange={(event) =>
                setForm({
                  ...initialForm,
                  accountType: event.target.value as AccountType,
                  openingOutstanding: event.target.value === "credit_card" ? "0" : "0",
                })
              }
            >
              {(Object.keys(accountTypeLabels) as AccountType[]).map((type) => (
                <option key={type} value={type}>
                  {accountTypeLabels[type]}
                </option>
              ))}
            </select>
          </label>

          <label>
            Account name
            <input value={form.name} onChange={(event) => updateForm("name", event.target.value)} required />
          </label>

          {form.accountType === "credit_card" ? (
            <>
              <label>
                Opening outstanding
                <input
                  inputMode="decimal"
                  placeholder="0"
                  value={form.openingOutstanding}
                  onChange={(event) => updateForm("openingOutstanding", event.target.value)}
                />
              </label>
              <label>
                Credit limit
                <input
                  inputMode="decimal"
                  placeholder="50000"
                  value={form.creditLimit}
                  onChange={(event) => updateForm("creditLimit", event.target.value)}
                  required
                />
              </label>
              <label>
                Cycle reset day
                <input
                  type="number"
                  min={1}
                  max={28}
                  value={form.billingDay}
                  onChange={(event) => updateForm("billingDay", event.target.value)}
                  required
                />
              </label>
              <label>
                Due day
                <input
                  type="number"
                  min={1}
                  max={28}
                  value={form.dueDay}
                  onChange={(event) => updateForm("dueDay", event.target.value)}
                  required
                />
              </label>
            </>
          ) : (
            <label>
              Opening balance
              <input
                inputMode="decimal"
                placeholder="0"
                value={form.openingBalance}
                onChange={(event) => updateForm("openingBalance", event.target.value)}
              />
            </label>
          )}

          {submitError ? <p className="form-message error form-wide">{submitError}</p> : null}
          {submitSuccess ? <p className="form-message success form-wide">{submitSuccess}</p> : null}

          <div className="form-actions form-wide">
            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create Account"}
            </button>
          </div>
        </form>
      </section>

      <section className="content-grid two-column">
        <div className="panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Liquid accounts</p>
              <h2>Bank, cash, and wallet</h2>
            </div>
          </div>

          {liquidAccounts.length === 0 ? (
            <EmptyState title="No liquid accounts yet" message="Add your first bank, cash, or wallet account." />
          ) : (
            <div className="card-list">
              {liquidAccounts.map((account) => (
                <article className="account-card" key={account.id}>
                  <div>
                    <h3>{account.name}</h3>
                    <p>{accountTypeLabels[account.account_type]}</p>
                  </div>
                  <dl className="detail-grid">
                    <div>
                      <dt>Opening balance</dt>
                      <dd>{formatMoney(account.opening_balance)}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{account.is_active ? "Active" : "Inactive"}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Credit cards</p>
              <h2>Card exposure</h2>
            </div>
          </div>

          {statementMessage ? <p className="form-message success">{statementMessage}</p> : null}

          {creditCardAccounts.length === 0 ? (
            <EmptyState title="No credit cards yet" message="Add a card to track billing-cycle exposure." />
          ) : (
            <div className="card-list">
              {creditCardAccounts.map((account) => {
                const exposure = cardsByAccountId.get(account.id);
                const utilization = exposure?.utilization_percentage ?? 0;
                return (
                  <article className="account-card" key={account.id}>
                    <div className="section-heading-row compact">
                      <div>
                        <h3>{account.name}</h3>
                        <p>{account.is_active ? "Active" : "Inactive"}</p>
                      </div>
                      <strong>{formatMoney(exposure?.outstanding ?? account.opening_outstanding)}</strong>
                    </div>
                    <dl className="detail-grid">
                      <div>
                        <dt>Credit limit</dt>
                        <dd>{formatMoney(exposure?.credit_limit ?? account.credit_limit)}</dd>
                      </div>
                      <div>
                        <dt>Available credit</dt>
                        <dd>{formatMoney(exposure?.available_credit ?? 0)}</dd>
                      </div>
                      <div>
                        <dt>Statement due</dt>
                        <dd>{formatMoney(exposure?.statement_balance_due ?? account.statement_balance)}</dd>
                      </div>
                      <div>
                        <dt>Unbilled balance</dt>
                        <dd>{formatMoney(exposure?.unbilled_balance ?? 0)}</dd>
                      </div>
                      <div>
                        <dt>Statement due date</dt>
                        <dd>
                          {exposure?.statement_due_date || account.statement_due_date
                            ? formatDate(exposure?.statement_due_date ?? account.statement_due_date ?? "")
                            : "Not set"}
                        </dd>
                      </div>
                      <div>
                        <dt>Current cycle spend</dt>
                        <dd>{formatMoney(exposure?.current_cycle_spend ?? 0)}</dd>
                      </div>
                      <div>
                        <dt>Reset / Due day</dt>
                        <dd>
                          Day {exposure?.billing_day ?? account.billing_day ?? "-"} / Day {exposure?.due_day ?? account.due_day ?? "-"}
                        </dd>
                      </div>
                      {exposure ? (
                        <div className="form-wide">
                          <dt>Cycle window</dt>
                          <dd>
                            {formatDate(exposure.cycle_start_date)} - {formatDate(exposure.cycle_end_date)}
                          </dd>
                        </div>
                      ) : null}
                    </dl>
                    <div className="utilization-row">
                      <span>Utilization {utilization}%</span>
                      <div className="progress-track slim" aria-hidden="true">
                        <span className="progress-fill" style={{ width: `${clampPercentage(utilization)}%` }} />
                      </div>
                    </div>

                    {editingStatementId === account.id ? (
                      <form
                        className="form-grid statement-edit-form"
                        onSubmit={(event) => void handleStatementSubmit(event, account, exposure)}
                      >
                        <label>
                          Current statement due
                          <input
                            inputMode="decimal"
                            value={statementAmount}
                            onChange={(event) => {
                              setStatementAmount(event.target.value);
                              setStatementError(null);
                            }}
                            autoFocus
                          />
                        </label>
                        <label>
                          Due date
                          <input
                            type="date"
                            value={statementDueDate}
                            onChange={(event) => {
                              setStatementDueDate(event.target.value);
                              setStatementError(null);
                            }}
                            disabled={moneyToNumber(statementAmount || "0") === 0}
                          />
                        </label>
                        <p className="helper-text form-wide">
                          Enter the amount still payable from the latest generated statement. Later card payments and refunds reduce it automatically.
                        </p>
                        {statementError ? <p className="form-message error form-wide">{statementError}</p> : null}
                        <div className="form-actions form-wide">
                          <button className="primary-button compact-button" type="submit" disabled={statementSubmitting}>
                            {statementSubmitting ? "Saving..." : "Save statement"}
                          </button>
                          <button className="secondary-button compact-button" type="button" onClick={cancelStatementEdit}>
                            Cancel
                          </button>
                        </div>
                      </form>
                    ) : (
                      <button
                        className="secondary-button compact-button card-action"
                        type="button"
                        onClick={() => startStatementEdit(account, exposure)}
                      >
                        Update statement
                      </button>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
