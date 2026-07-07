"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { CategorySetupWarning } from "@/components/ui/SetupWarning";
import {
  createCommitment,
  getAccounts,
  getCategories,
  getCommitments,
  getErrorMessage,
  getFinancialProfile,
  updateFinancialProfile,
} from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { formatMoney, isValidMoneyInput, isValidNonNegativeMoneyInput } from "@/lib/money";
import type { Account, Category, Commitment, CommitmentCreatePayload, CommitmentType, FinancialProfile } from "@/lib/types";

interface ProfileFormState {
  monthlySavingsTarget: string;
  salaryDay: string;
}

interface CommitmentFormState {
  name: string;
  amount: string;
  commitmentType: CommitmentType;
  accountId: string;
  categoryId: string;
  dueDay: string;
}

const initialProfileForm: ProfileFormState = {
  monthlySavingsTarget: "0",
  salaryDay: "1",
};

const initialCommitmentForm: CommitmentFormState = {
  name: "",
  amount: "",
  commitmentType: "fixed_expense",
  accountId: "",
  categoryId: "",
  dueDay: "",
};

const commitmentTypeLabels: Record<CommitmentType, string> = {
  fixed_expense: "Fixed expense",
  investment: "Investment",
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

function accountName(accountsById: Map<string, Account>, accountId: string): string {
  return accountsById.get(accountId)?.name ?? "Unknown account";
}

function categoryName(categoriesById: Map<string, Category>, categoryId: string): string {
  return categoriesById.get(categoryId)?.name ?? "Unknown category";
}

export function SettingsClient() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileFormState>(initialProfileForm);
  const [commitmentForm, setCommitmentForm] = useState<CommitmentFormState>(initialCommitmentForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [commitmentError, setCommitmentError] = useState<string | null>(null);
  const [commitmentSuccess, setCommitmentSuccess] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [creatingCommitment, setCreatingCommitment] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [loadedProfile, loadedAccounts, loadedCategories, loadedCommitments] = await Promise.all([
        getFinancialProfile(),
        getAccounts(),
        getCategories(),
        getCommitments(),
      ]);

      setProfile(loadedProfile);
      setAccounts(loadedAccounts);
      setCategories(loadedCategories);
      setCommitments(loadedCommitments);
      setProfileForm({
        monthlySavingsTarget: loadedProfile ? String(loadedProfile.monthly_savings_target) : "0",
        salaryDay: loadedProfile ? String(loadedProfile.salary_day) : "1",
      });
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const activeAccounts = useMemo(() => accounts.filter((account) => account.is_active), [accounts]);
  const commitmentAccountOptions = useMemo(() => {
    if (commitmentForm.commitmentType === "investment") {
      return activeAccounts.filter((account) => account.account_type !== "credit_card");
    }

    return activeAccounts;
  }, [activeAccounts, commitmentForm.commitmentType]);
  const accountsById = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts]);
  const categoriesById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

  useEffect(() => {
    const selectedAccount = commitmentForm.accountId ? accountsById.get(commitmentForm.accountId) : undefined;
    if (commitmentForm.commitmentType === "investment" && selectedAccount?.account_type === "credit_card") {
      setCommitmentForm((current) => ({ ...current, accountId: "" }));
    }
  }, [accountsById, commitmentForm.accountId, commitmentForm.commitmentType]);

  function updateProfileForm<K extends keyof ProfileFormState>(key: K, value: ProfileFormState[K]) {
    setProfileForm((current) => ({ ...current, [key]: value }));
    setProfileError(null);
    setProfileSuccess(null);
  }

  function updateCommitmentForm<K extends keyof CommitmentFormState>(key: K, value: CommitmentFormState[K]) {
    setCommitmentForm((current) => ({ ...current, [key]: value }));
    setCommitmentError(null);
    setCommitmentSuccess(null);
  }

  function handleCommitmentTypeChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextType = event.target.value as CommitmentType;
    setCommitmentForm((current) => ({
      ...current,
      commitmentType: nextType,
      accountId: nextType === "investment" && accountsById.get(current.accountId)?.account_type === "credit_card" ? "" : current.accountId,
    }));
    setCommitmentError(null);
    setCommitmentSuccess(null);
  }

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileError(null);
    setProfileSuccess(null);

    const salaryDay = parseDay(profileForm.salaryDay);
    if (profileForm.monthlySavingsTarget.trim() && !isValidNonNegativeMoneyInput(profileForm.monthlySavingsTarget)) {
      setProfileError("Enter monthly savings target as a rupee amount.");
      return;
    }
    if (salaryDay === null) {
      setProfileError("Enter a salary day from 1 to 28.");
      return;
    }

    setSavingProfile(true);
    try {
      const saved = await updateFinancialProfile({
        monthly_savings_target: profileForm.monthlySavingsTarget.trim() || "0",
        salary_day: salaryDay,
      });
      setProfile(saved);
      setProfileForm({ monthlySavingsTarget: String(saved.monthly_savings_target), salaryDay: String(saved.salary_day) });
      setProfileSuccess("Financial profile saved.");
    } catch (saveError) {
      setProfileError(getErrorMessage(saveError));
    } finally {
      setSavingProfile(false);
    }
  }

  function validateCommitmentForm(): string | null {
    if (!commitmentForm.name.trim()) {
      return "Enter a commitment name.";
    }
    if (!isValidMoneyInput(commitmentForm.amount)) {
      return "Enter a commitment amount like 1200 or 1200.00.";
    }
    if (!commitmentForm.accountId) {
      return "Choose an account.";
    }
    if (!commitmentForm.categoryId) {
      return "Choose a category.";
    }
    if (parseDay(commitmentForm.dueDay) === null) {
      return "Enter a due day from 1 to 28.";
    }

    const selectedAccount = accountsById.get(commitmentForm.accountId);
    if (commitmentForm.commitmentType === "investment" && selectedAccount?.account_type === "credit_card") {
      return "Credit cards cannot be used for investment commitments.";
    }

    return null;
  }

  async function handleCommitmentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCommitmentError(null);
    setCommitmentSuccess(null);

    const validationError = validateCommitmentForm();
    const dueDay = parseDay(commitmentForm.dueDay);
    if (validationError || dueDay === null) {
      setCommitmentError(validationError ?? "Enter a due day from 1 to 28.");
      return;
    }

    const payload: CommitmentCreatePayload = {
      name: commitmentForm.name.trim(),
      amount: commitmentForm.amount.trim(),
      commitment_type: commitmentForm.commitmentType,
      account_id: commitmentForm.accountId,
      category_id: commitmentForm.categoryId,
      due_day: dueDay,
      is_active: true,
    };

    setCreatingCommitment(true);
    try {
      await createCommitment(payload);
      setCommitmentSuccess("Recurring commitment created.");
      setCommitmentForm(initialCommitmentForm);
      setCommitments(await getCommitments());
    } catch (createError) {
      setCommitmentError(getErrorMessage(createError));
    } finally {
      setCreatingCommitment(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading settings" rows={4} />;
  }

  if (error) {
    return <ErrorState title="Unable to load settings" message={error} onRetry={loadSettings} />;
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Configuration</p>
          <h1>Settings</h1>
          <p>Set your savings target and recurring commitments used by the existing Safe to Spend engine.</p>
        </div>
      </header>

      {categories.length === 0 ? <CategorySetupWarning /> : null}

      <section className="panel form-panel">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Financial profile</p>
            <h2>{profile ? "Update profile" : "No financial profile"}</h2>
          </div>
          {profile ? <span className="muted-text">Updated {formatDate(profile.updated_at)}</span> : null}
        </div>
        <p className="helper-text">
          The savings target is reserved by Safe to Spend until recorded investment transactions complete it. Salary is
          only reflected after an income transaction is recorded.
        </p>

        <form className="form-grid" onSubmit={handleProfileSubmit}>
          <label>
            Monthly savings target
            <input
              inputMode="decimal"
              value={profileForm.monthlySavingsTarget}
              onChange={(event) => updateProfileForm("monthlySavingsTarget", event.target.value)}
            />
          </label>
          <label>
            Salary day
            <input
              type="number"
              min={1}
              max={28}
              value={profileForm.salaryDay}
              onChange={(event) => updateProfileForm("salaryDay", event.target.value)}
              required
            />
          </label>
          {profileError ? <p className="form-message error form-wide">{profileError}</p> : null}
          {profileSuccess ? <p className="form-message success form-wide">{profileSuccess}</p> : null}
          <div className="form-actions form-wide">
            <button className="primary-button" type="submit" disabled={savingProfile}>
              {savingProfile ? "Saving..." : "Save Financial Profile"}
            </button>
          </div>
        </form>
      </section>

      <section className="content-grid two-column">
        <div className="panel form-panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Recurring commitments</p>
              <h2>Create commitment</h2>
            </div>
          </div>

          <form className="form-grid single-column" onSubmit={handleCommitmentSubmit}>
            <label>
              Name
              <input value={commitmentForm.name} onChange={(event) => updateCommitmentForm("name", event.target.value)} required />
            </label>
            <label>
              Amount
              <input
                inputMode="decimal"
                placeholder="1200"
                value={commitmentForm.amount}
                onChange={(event) => updateCommitmentForm("amount", event.target.value)}
                required
              />
            </label>
            <label>
              Commitment type
              <select value={commitmentForm.commitmentType} onChange={handleCommitmentTypeChange}>
                {(Object.keys(commitmentTypeLabels) as CommitmentType[]).map((type) => (
                  <option key={type} value={type}>
                    {commitmentTypeLabels[type]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Account
              <select value={commitmentForm.accountId} onChange={(event) => updateCommitmentForm("accountId", event.target.value)} required>
                <option value="">Choose account</option>
                {commitmentAccountOptions.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name} ({account.account_type.replace("_", " ")})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Category
              <select value={commitmentForm.categoryId} onChange={(event) => updateCommitmentForm("categoryId", event.target.value)} required>
                <option value="">Choose category</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Due day
              <input
                type="number"
                min={1}
                max={28}
                value={commitmentForm.dueDay}
                onChange={(event) => updateCommitmentForm("dueDay", event.target.value)}
                required
              />
            </label>
            {commitmentError ? <p className="form-message error">{commitmentError}</p> : null}
            {commitmentSuccess ? <p className="form-message success">{commitmentSuccess}</p> : null}
            <div className="form-actions">
              <button className="primary-button" type="submit" disabled={creatingCommitment}>
                {creatingCommitment ? "Creating..." : "Create Commitment"}
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Existing commitments</p>
              <h2>Reserved obligations</h2>
            </div>
          </div>

          {commitments.length === 0 ? (
            <EmptyState title="No commitments yet" message="Create fixed expenses and monthly investments to reserve them in Safe to Spend." />
          ) : (
            <div className="card-list">
              {commitments.map((commitment) => (
                <article className="account-card" key={commitment.id}>
                  <div className="section-heading-row compact">
                    <div>
                      <h3>{commitment.name}</h3>
                      <p>{commitmentTypeLabels[commitment.commitment_type]}</p>
                    </div>
                    <strong>{formatMoney(commitment.amount)}</strong>
                  </div>
                  <dl className="detail-grid">
                    <div>
                      <dt>Category</dt>
                      <dd>{categoryName(categoriesById, commitment.category_id)}</dd>
                    </div>
                    <div>
                      <dt>Account</dt>
                      <dd>{accountName(accountsById, commitment.account_id)}</dd>
                    </div>
                    <div>
                      <dt>Due day</dt>
                      <dd>Day {commitment.due_day}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{commitment.is_active ? "Active" : "Inactive"}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
