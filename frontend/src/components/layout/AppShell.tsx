"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
        <Link className="primary-button sidebar-action" href="/transactions?add=transaction">
          Add Transaction
        </Link>
      </aside>

      <div className="mobile-header">
        <Link className="mobile-brand" href="/">
          <span className="brand-mark">SL</span>
          <span>SpendLens</span>
        </Link>
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
