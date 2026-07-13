"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/transactions", label: "Transactions" },
  { href: "/accounts", label: "Accounts" },
  { href: "/settings", label: "Settings" },
];

function isActiveRoute(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname.startsWith(href);
}

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const isLoginRoute = pathname === "/login";
  const [authState, setAuthState] = useState<"checking" | "authenticated" | "unauthenticated">("checking");

  useEffect(() => {
    if (isLoginRoute) {
      return;
    }

    let active = true;
    void fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => {
        const body = (await response.json()) as { authenticated?: boolean };
        if (!active) {
          return;
        }

        if (response.ok && body.authenticated) {
          setAuthState("authenticated");
          return;
        }

        setAuthState("unauthenticated");
        router.replace("/login");
      })
      .catch(() => {
        if (active) {
          setAuthState("unauthenticated");
          router.replace("/login");
        }
      });

    return () => {
      active = false;
    };
  }, [isLoginRoute, router]);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    setAuthState("unauthenticated");
    router.replace("/login");
    router.refresh();
  }

  if (isLoginRoute) {
    return <main className="login-page">{children}</main>;
  }

  if (authState !== "authenticated") {
    return (
      <main className="auth-loading">
        <span className="brand-mark">SL</span>
        <p>Checking private access...</p>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <Link className="brand" href="/">
          <span className="brand-mark">SL</span>
          <span>
            <strong>SpendLens</strong>
            <small>Know what is actually safe to spend.</small>
          </span>
        </Link>
        <nav className="nav-list">
          {navItems.map((item) => (
            <Link
              aria-current={isActiveRoute(pathname, item.href) ? "page" : undefined}
              className={isActiveRoute(pathname, item.href) ? "nav-link active" : "nav-link"}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-actions">
          <Link className="primary-button" href="/transactions?add=transaction">
            Add Transaction
          </Link>
          <button className="secondary-button" onClick={() => void signOut()} type="button">
            Sign out
          </button>
        </div>
      </aside>

      <div className="mobile-header">
        <Link className="mobile-brand" href="/">
          <span className="brand-mark">SL</span>
          <span>SpendLens</span>
        </Link>
        <button className="secondary-button compact-button" onClick={() => void signOut()} type="button">
          Sign out
        </button>
      </div>

      <main className="main-content">{children}</main>

      <Link className="mobile-add-action" href="/transactions?add=transaction" aria-label="Add transaction">
        Add
      </Link>

      <nav className="bottom-nav" aria-label="Mobile navigation">
        {navItems.map((item) => (
          <Link
            aria-current={isActiveRoute(pathname, item.href) ? "page" : undefined}
            className={isActiveRoute(pathname, item.href) ? "bottom-nav-link active" : "bottom-nav-link"}
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
