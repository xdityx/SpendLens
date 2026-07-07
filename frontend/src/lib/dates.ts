const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const timezoneSuffixPattern = /(Z|[+-]\d{2}:?\d{2})$/i;

function parseApiDateTime(value: string): Date {
  const normalized = timezoneSuffixPattern.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

export function localDateTimeInputToUtcIso(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Enter a valid occurred-at date and time.");
  }

  return parsed.toISOString();
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Not recorded";
  }

  const parsed = parseApiDateTime(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return dateTimeFormatter.format(parsed);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Not recorded";
  }

  const parsed = parseApiDateTime(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return dateFormatter.format(parsed);
}

export function maxDateTimeLocalNow(): string {
  const now = new Date();
  now.setSeconds(0, 0);
  const offsetMs = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 16);
}
