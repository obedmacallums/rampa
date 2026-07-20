import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { MemberRole } from "../api/client";
import { useMembers } from "../stores/members";
import { useSession } from "../stores/session";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import Field from "../ui/Field";

// Member panel (002 US3): every member sees the list with its audit columns
// (FR-007/FR-009); management controls render only for owners. Adding a
// teammate never leaves the project page (SC-006).
export default function ProjectMembers({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const { user } = useSession();
  const { members, error, load, add, updateRole, remove } = useMembers();
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);

  useEffect(() => {
    void load(projectId);
  }, [projectId, load]);

  const isOwner = members.some((m) => m.username === user?.username && m.role === "owner");
  const roleLabel = (r: MemberRole) => t(r === "owner" ? "members.role_owner" : "members.role_member");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim()) return;
    if (await add(projectId, username.trim(), role)) {
      setUsername("");
      setRole("member");
    }
  };

  return (
    <section className="grid gap-4">
      <h2 className="text-lg font-semibold text-text-strong">{t("members.title")}</h2>
      <ul className="grid gap-2">
        {members.map((member) => (
          <li
            key={member.username}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-surface-2 bg-surface-1 px-4 py-2.5 text-sm"
          >
            <span className="font-medium text-text-strong">{member.username}</span>
            <span
              className={
                member.role === "owner"
                  ? "rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-xs text-accent"
                  : "rounded-full border border-surface-2 px-2 py-0.5 text-xs text-text-muted"
              }
            >
              {roleLabel(member.role)}
            </span>
            <span className="text-xs text-text-muted">
              {member.granted_by ?? t("members.granted_by_system")},{" "}
              {new Date(member.granted_at).toLocaleDateString(i18n.language)}
            </span>
            {isOwner && (
              <span className="ml-auto flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() =>
                    void updateRole(
                      projectId,
                      member.username,
                      member.role === "owner" ? "member" : "owner",
                    )
                  }
                >
                  {t(member.role === "owner" ? "members.revoke_owner" : "members.grant_owner")}
                </Button>
                <Button variant="danger" onClick={() => setRemoveTarget(member.username)}>
                  {t("members.remove")}
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>

      {isOwner && (
        <form
          onSubmit={(e) => void submit(e)}
          className="flex flex-wrap items-end gap-3 rounded-lg border border-surface-2 bg-surface-1 p-4"
        >
          <Field label={t("members.add_label")}>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("auth.username")}
            />
          </Field>
          <select value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
            <option value="member">{t("members.role_member")}</option>
            <option value="owner">{t("members.role_owner")}</option>
          </select>
          <Button type="submit" variant="secondary">
            {t("members.add_label")}
          </Button>
        </form>
      )}

      {error && <Alert>{t(error)}</Alert>}

      <ConfirmDialog
        open={removeTarget !== null}
        message={removeTarget ? t("members.remove_confirm", { username: removeTarget }) : ""}
        confirmLabel={t("members.remove")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => {
          if (removeTarget) void remove(projectId, removeTarget);
          setRemoveTarget(null);
        }}
        onCancel={() => setRemoveTarget(null)}
      />
    </section>
  );
}
