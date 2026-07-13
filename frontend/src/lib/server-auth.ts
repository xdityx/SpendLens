import "server-only";

import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE_NAME = "spendlens_session";
export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

const DEVELOPMENT_LOGIN_PASSWORD = "spendlens-local";
const DEVELOPMENT_SESSION_SECRET = "spendlens-local-development-session-secret";

function configuredValue(name: "SPENDLENS_LOGIN_PASSWORD" | "SPENDLENS_SESSION_SECRET", developmentFallback: string): string {
  const configured = process.env[name]?.trim();
  if (configured) {
    return configured;
  }

  return process.env.NODE_ENV === "production" ? "" : developmentFallback;
}

function sessionSecret(): string {
  return configuredValue("SPENDLENS_SESSION_SECRET", DEVELOPMENT_SESSION_SECRET);
}

function digest(value: string): Buffer {
  return createHash("sha256").update(value).digest();
}

function signature(expiresAt: string, secret: string): string {
  return createHmac("sha256", secret).update(expiresAt).digest("base64url");
}

export function hasProductionAuthConfiguration(): boolean {
  const secret = sessionSecret();
  const password = configuredValue("SPENDLENS_LOGIN_PASSWORD", DEVELOPMENT_LOGIN_PASSWORD);
  return secret.length >= 32 && password.length >= 12;
}

export function verifyLoginPassword(password: string): boolean {
  const expected = configuredValue("SPENDLENS_LOGIN_PASSWORD", DEVELOPMENT_LOGIN_PASSWORD);
  if (!expected) {
    return false;
  }

  return timingSafeEqual(digest(password), digest(expected));
}

export function createSessionToken(): string {
  const secret = sessionSecret();
  if (!secret) {
    throw new Error("SPENDLENS_SESSION_SECRET is not configured");
  }

  const expiresAt = String(Date.now() + SESSION_MAX_AGE_SECONDS * 1000);
  return `${expiresAt}.${signature(expiresAt, secret)}`;
}

export function verifySessionToken(token: string | undefined): boolean {
  const secret = sessionSecret();
  if (!token || !secret) {
    return false;
  }

  const [expiresAt, suppliedSignature, extra] = token.split(".");
  if (!expiresAt || !suppliedSignature || extra || !/^\d+$/.test(expiresAt) || Number(expiresAt) <= Date.now()) {
    return false;
  }

  const expectedSignature = signature(expiresAt, secret);
  return timingSafeEqual(digest(suppliedSignature), digest(expectedSignature));
}
