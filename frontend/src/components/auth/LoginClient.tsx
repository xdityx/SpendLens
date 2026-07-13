"use client";

import { FormEvent, useState } from "react";


export function LoginClient() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await fetch("/api/auth/login", {
        body: JSON.stringify({ password }),
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const body = (await response.json()) as { detail?: string };

      if (!response.ok) {
        setError(body.detail || "Unable to sign in.");
        return;
      }

      window.location.assign("/");
    } catch {
      setError("Unable to reach SpendLens.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="login-panel">
      <div className="login-brand">
        <span className="brand-mark">SL</span>
        <div>
          <p className="eyebrow">Private access</p>
          <h1>SpendLens</h1>
        </div>
      </div>

      <form className="form-grid single-column" onSubmit={handleSubmit}>
        <label>
          Password
          <input
            autoComplete="current-password"
            autoFocus
            onChange={(event) => {
              setPassword(event.target.value);
              setError(null);
            }}
            type="password"
            value={password}
          />
        </label>
        {error ? <p className="form-message error">{error}</p> : null}
        <button className="primary-button" disabled={submitting || !password} type="submit">
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}
