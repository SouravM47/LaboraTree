"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-forest text-sm text-white">
              ▲
            </span>
            <span className="font-display text-lg font-semibold text-forest">Laboratree</span>
            <span className="hidden text-xs uppercase tracking-widest text-leaf sm:inline">
              Grow · Innovate · Impact
            </span>
          </Link>
          {user ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted">{user.email}</span>
              <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">
                {user.role}
              </span>
              <button
                onClick={logout}
                className="rounded-lg border border-line px-3 py-1 text-forest hover:bg-bg"
              >
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
      <footer className="border-t border-line py-4 text-center text-xs text-muted">
        Laboratree · v0.1
      </footer>
    </div>
  );
}
