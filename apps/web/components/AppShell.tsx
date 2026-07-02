"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import BrandMark from "@/components/BrandMark";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <BrandMark size={40} />
            <span className="flex items-baseline gap-3">
              <span className="font-display text-2xl font-semibold tracking-tight">
                <span className="text-forest">Labora</span>
                <span className="text-leaf">tree</span>
              </span>
              <span className="hidden text-[11px] font-medium uppercase tracking-[0.25em] text-leaf sm:inline">
                Grow · Innovate · Impact
              </span>
            </span>
          </Link>
          {user ? (
            <div className="flex items-center gap-4 text-sm">
              <Link href="/" className="font-medium text-forest hover:text-leaf">
                Projects
              </Link>
              <Link href="/team" className="font-medium text-forest hover:text-leaf">
                Team
              </Link>
              <span className="hidden text-muted md:inline">{user.email}</span>
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
