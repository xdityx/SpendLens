import type {
  Account,
  AccountCreatePayload,
  CardStatementUpdatePayload,
  Category,
  Commitment,
  CommitmentCreatePayload,
  CommitmentStatus,
  CommitmentUpdatePayload,
  CreditCardExposure,
  DashboardSummary,
  EMIPlan,
  EMIPlanCreatePayload,
  EMIPlanStatus,
  EMIPlanUpdatePayload,
  FinancialProfile,
  FinancialProfilePayload,
  Transaction,
  TransactionCreatePayload,
  TransactionFilters,
  TransactionUpdatePayload,
} from "./types";

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status = 0, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function apiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!value) {
    throw new ApiError("NEXT_PUBLIC_API_BASE_URL is not configured. Set it to the browser-facing FastAPI URL.");
  }

  return value.replace(/\/$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (isRecord(item) && typeof item.msg === "string") {
          const location = Array.isArray(item.loc) ? item.loc.join(".") : "field";
          return `${location}: ${item.msg}`;
        }
        return null;
      })
      .filter((message): message is string => message !== null);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (isRecord(detail) && typeof detail.message === "string") {
    return detail.message;
  }

  return "The API returned an error.";
}

async function readResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text.length > 0 ? text : null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  const headers = new Headers(init.headers);

  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  headers.set("Accept", "application/json");

  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    throw new ApiError("SpendLens API is unavailable. Confirm the FastAPI service is running.", 0, error);
  }

  const body = await readResponseBody(response);

  if (!response.ok) {
    const detail = isRecord(body) && "detail" in body ? body.detail : body;
    throw new ApiError(detailMessage(detail), response.status, detail);
  }

  return body as T;
}

function buildQuery(params: object): string {
  const searchParams = new URLSearchParams();

  Object.entries(params as Record<string, string | number | boolean | undefined>).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query.length > 0 ? `?${query}` : "";
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong.";
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>("/api/v1/dashboard/summary");
}

export function getCardExposure(): Promise<CreditCardExposure[]> {
  return request<CreditCardExposure[]>("/api/v1/cards/exposure");
}

export function getAccounts(): Promise<Account[]> {
  return request<Account[]>("/api/v1/accounts");
}

export function createAccount(payload: AccountCreatePayload): Promise<Account> {
  return request<Account>("/api/v1/accounts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCardStatement(accountId: string, payload: CardStatementUpdatePayload): Promise<Account> {
  return request<Account>("/api/v1/accounts/" + accountId + "/statement", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getCategories(): Promise<Category[]> {
  return request<Category[]>("/api/v1/categories");
}

export function getTransactions(filters: TransactionFilters = {}): Promise<Transaction[]> {
  return request<Transaction[]>(`/api/v1/transactions${buildQuery(filters)}`);
}

export function createTransaction(payload: TransactionCreatePayload): Promise<Transaction> {
  return request<Transaction>("/api/v1/transactions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTransaction(transactionId: string, payload: TransactionUpdatePayload): Promise<Transaction> {
  return request<Transaction>("/api/v1/transactions/" + transactionId, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function voidTransaction(transactionId: string): Promise<Transaction> {
  return request<Transaction>("/api/v1/transactions/" + transactionId, {
    method: "DELETE",
  });
}

export function getCommitments(): Promise<Commitment[]> {
  return request<Commitment[]>("/api/v1/commitments");
}

export function createCommitment(payload: CommitmentCreatePayload): Promise<Commitment> {
  return request<Commitment>("/api/v1/commitments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCommitment(commitmentId: string, payload: CommitmentUpdatePayload): Promise<Commitment> {
  return request<Commitment>(`/api/v1/commitments/${commitmentId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getCommitmentStatuses(asOf?: string): Promise<CommitmentStatus[]> {
  return request<CommitmentStatus[]>(`/api/v1/commitments/status${buildQuery({ as_of: asOf })}`);
}

export function getEmiPlans(): Promise<EMIPlan[]> {
  return request<EMIPlan[]>("/api/v1/emi-plans");
}

export function getEmiPlanStatuses(asOf?: string): Promise<EMIPlanStatus[]> {
  return request<EMIPlanStatus[]>(`/api/v1/emi-plans/status${buildQuery({ as_of: asOf })}`);
}

export function createEmiPlan(payload: EMIPlanCreatePayload): Promise<EMIPlan> {
  return request<EMIPlan>("/api/v1/emi-plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateEmiPlan(emiPlanId: string, payload: EMIPlanUpdatePayload): Promise<EMIPlan> {
  return request<EMIPlan>(`/api/v1/emi-plans/${emiPlanId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getFinancialProfile(): Promise<FinancialProfile | null> {
  return request<FinancialProfile | null>("/api/v1/financial-profile");
}

export function updateFinancialProfile(payload: FinancialProfilePayload): Promise<FinancialProfile> {
  return request<FinancialProfile>("/api/v1/financial-profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
