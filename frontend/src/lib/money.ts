import type { MoneyValue, TransactionType } from "./types";

const moneyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const moneyInputPattern = /^\d+(\.\d{1,2})?$/;

export function moneyToNumber(value: MoneyValue | null | undefined): number {
  if (value === null || value === undefined) {
    return 0;
  }

  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatMoney(value: MoneyValue | null | undefined): string {
  return moneyFormatter.format(moneyToNumber(value));
}

export function formatMoneyWithoutSign(value: MoneyValue | null | undefined): string {
  return formatMoney(Math.abs(moneyToNumber(value)));
}

function hasPositiveMoneyValue(value: string): boolean {
  const [whole, cents = ""] = value.split(".");
  const wholeHasValue = whole.replace(/^0+/, "").length > 0;
  const centsHasValue = cents.replace(/0+$/, "").length > 0;
  return wholeHasValue || centsHasValue;
}

export function isValidMoneyInput(value: string): boolean {
  const trimmed = value.trim();
  return moneyInputPattern.test(trimmed) && hasPositiveMoneyValue(trimmed);
}

export function isValidNonNegativeMoneyInput(value: string): boolean {
  const trimmed = value.trim();
  return moneyInputPattern.test(trimmed);
}

export function clampPercentage(value: MoneyValue | null | undefined): number {
  const parsed = moneyToNumber(value);
  if (parsed < 0) {
    return 0;
  }
  if (parsed > 100) {
    return 100;
  }
  return parsed;
}

export function transactionAmountDisplay(type: TransactionType, amount: MoneyValue): { label: string; tone: string } {
  if (type === "expense" || type === "investment") {
    return { label: `-${formatMoneyWithoutSign(amount)}`, tone: "negative" };
  }

  if (type === "income" || type === "refund") {
    return { label: `+${formatMoneyWithoutSign(amount)}`, tone: "positive" };
  }

  return { label: formatMoneyWithoutSign(amount), tone: "neutral" };
}
