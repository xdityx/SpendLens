export type MoneyValue = string | number;

export type AccountType = "bank" | "cash" | "wallet" | "credit_card";

export type TransactionType = "expense" | "income" | "transfer" | "investment" | "refund";

export type CommitmentType = "fixed_expense" | "investment";

export type CommitmentMonthlyStatus = "paid" | "partial" | "overdue_partial" | "upcoming" | "due_today" | "overdue";

export type EMISetupCurrentMonthState = "not_posted" | "included_in_opening_liability" | "settled_before_tracking";

export type EMICurrentMonthStatus =
  | "included_in_card_liability"
  | "settled_before_tracking"
  | "posted"
  | "upcoming"
  | "due_today"
  | "overdue"
  | "completed";

export type DashboardStatus = "available" | "fully_allocated" | "overcommitted" | string;

export interface Account {
  id: string;
  name: string;
  account_type: AccountType;
  opening_balance: MoneyValue;
  opening_outstanding: MoneyValue;
  credit_limit: MoneyValue | null;
  billing_day: number | null;
  due_day: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AccountCreatePayload {
  name: string;
  account_type: AccountType;
  opening_balance: string;
  opening_outstanding: string;
  credit_limit?: string | null;
  billing_day?: number | null;
  due_day?: number | null;
  is_active?: boolean;
}

export interface Category {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface Transaction {
  id: string;
  transaction_type: TransactionType;
  amount: MoneyValue;
  source_account_id: string | null;
  destination_account_id: string | null;
  category_id: string | null;
  recurring_commitment_id: string | null;
  emi_plan_id: string | null;
  merchant: string | null;
  description: string | null;
  occurred_at: string;
  created_at: string;
}

export interface TransactionCreatePayload {
  transaction_type: TransactionType;
  amount: string;
  source_account_id?: string | null;
  destination_account_id?: string | null;
  category_id?: string | null;
  recurring_commitment_id?: string | null;
  emi_plan_id?: string | null;
  merchant?: string | null;
  description?: string | null;
  occurred_at?: string | null;
}

export interface TransactionFilters {
  account_id?: string;
  transaction_type?: TransactionType;
  category_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface Commitment {
  id: string;
  name: string;
  amount: MoneyValue;
  category_id: string;
  account_id: string;
  commitment_type: CommitmentType;
  due_day: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CommitmentCreatePayload {
  name: string;
  amount: string;
  category_id: string;
  account_id: string;
  commitment_type: CommitmentType;
  due_day: number;
  is_active?: boolean;
}

export interface CommitmentUpdatePayload {
  name: string;
  amount: string;
  category_id: string;
  account_id: string;
  due_day: number;
  is_active: boolean;
}

export interface CommitmentStatus {
  commitment_id: string;
  name: string;
  amount: MoneyValue;
  category_id: string;
  account_id: string;
  due_day: number;
  due_date: string;
  paid_amount_this_month: MoneyValue;
  remaining_amount_this_month: MoneyValue;
  status: CommitmentMonthlyStatus;
  fulfilled_at: string | null;
}

export interface EMIPlan {
  id: string;
  name: string;
  account_id: string;
  category_id: string;
  monthly_installment: MoneyValue;
  remaining_amount_at_setup: MoneyValue;
  due_day: number;
  tracking_start_month: string;
  setup_current_month_state: EMISetupCurrentMonthState;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  financial_configuration_locked: boolean;
  financial_configuration_lock_reason: string | null;
}

export interface EMIPlanCreatePayload {
  name: string;
  account_id: string;
  category_id: string;
  monthly_installment: string;
  remaining_amount_at_setup: string;
  due_day: number;
  setup_current_month_state: EMISetupCurrentMonthState;
}

export interface EMIPlanUpdatePayload {
  name: string;
  account_id: string;
  category_id: string;
  monthly_installment: string;
  remaining_amount_at_setup: string;
  due_day: number;
  setup_current_month_state: EMISetupCurrentMonthState;
  is_active: boolean;
}

export interface EMIPlanStatus {
  emi_plan_id: string;
  name: string;
  account_id: string;
  category_id: string;
  monthly_installment: MoneyValue;
  remaining_amount_at_setup: MoneyValue;
  installment_month: string;
  current_installment_amount: MoneyValue;
  current_month_status: EMICurrentMonthStatus;
  current_month_reserve: MoneyValue;
  remaining_unrecognized_amount: MoneyValue;
  future_remaining_after_current_installment: MoneyValue;
  due_day: number;
  due_date: string;
  posted_at: string | null;
  is_active: boolean;
}

export interface FinancialProfile {
  id: string;
  monthly_savings_target: MoneyValue;
  salary_day: number;
  created_at: string;
  updated_at: string;
}

export interface FinancialProfilePayload {
  monthly_savings_target: string;
  salary_day: number;
}

export interface DashboardSummary {
  liquid_cash: MoneyValue;
  credit_card_liability: MoneyValue;
  remaining_fixed_commitments: MoneyValue;
  remaining_emi_installments: MoneyValue;
  monthly_savings_target: MoneyValue;
  savings_completed_this_month: MoneyValue;
  remaining_savings_target: MoneyValue;
  safe_to_spend: MoneyValue;
  status: DashboardStatus;
}

export interface CreditCardExposure {
  account_id: string;
  account_name: string;
  credit_limit: MoneyValue;
  outstanding: MoneyValue;
  available_credit: MoneyValue;
  utilization_percentage: MoneyValue;
  current_cycle_spend: MoneyValue;
  billing_day: number;
  due_day: number;
}
