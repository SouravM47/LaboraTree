"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Api, getOrg, ROLES, type Member } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";

export default function TeamPage() {
  const { user, loading } = useRequireAuth();
  const { user: me } = useAuth();
  const orgId = getOrg() ?? "";
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("analyst");
  const [error, setError] = useState<string | null>(null);

  const canManage = me?.role === "owner" || me?.role === "admin";
  const canGrantOwner = me?.role === "owner";
  const roleOptions = ROLES.filter((r) => r !== "owner" || canGrantOwner);

  useEffect(() => {
    if (user && orgId) Api.listMembers(orgId).then(setMembers).catch(() => setMembers([]));
  }, [user, orgId]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const m = await Api.addMember(orgId, email.trim(), role);
      setMembers((prev) => [...prev, m]);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    }
  }

  async function changeRole(userId: string, newRole: string) {
    try {
      const m = await Api.setMemberRole(orgId, userId, newRole);
      setMembers((prev) => prev.map((x) => (x.user_id === userId ? m : x)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    }
  }

  if (loading || !user) return <p className="text-muted">Loading…</p>;

  return (
    <div>
      <Link href="/" className="text-sm text-muted hover:text-forest">
        ← Projects
      </Link>
      <h1 className="mt-2 font-display text-3xl text-forest">Team</h1>
      <p className="mt-1 text-muted">
        Everyone in your organization and their role.{" "}
        {canManage ? "You can add members and change roles." : "Only owners/admins can manage roles."}
      </p>

      {canManage && (
        <form onSubmit={add} className="mt-6 flex flex-wrap gap-2">
          <input
            type="email"
            required
            placeholder="person@company.com (must be registered)"
            className="min-w-64 flex-1 rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <select
            className="rounded-lg border border-line px-3 py-2"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {roleOptions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90">
            Add member
          </button>
        </form>
      )}
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-6 overflow-hidden rounded-2xl border border-line bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-muted">
            <tr>
              <th className="px-5 py-3">Name</th>
              <th className="px-5 py-3">Email</th>
              <th className="px-5 py-3">Role</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id} className="border-b border-line/60">
                <td className="px-5 py-3 text-ink">{m.full_name || "—"}</td>
                <td className="px-5 py-3 text-muted">{m.email}</td>
                <td className="px-5 py-3">
                  {canManage && m.user_id !== me?.id ? (
                    <select
                      className="rounded-lg border border-line px-2 py-1"
                      value={m.role}
                      onChange={(e) => changeRole(m.user_id, e.target.value)}
                    >
                      {roleOptions.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">
                      {m.role}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
