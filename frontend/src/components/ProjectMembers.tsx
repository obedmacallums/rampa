import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { MemberRole } from "../api/client";
import { useMembers } from "../stores/members";
import { useSession } from "../stores/session";

// Member panel (002 US3): every member sees the list with its audit columns
// (FR-007/FR-009); management controls render only for owners. Adding a
// teammate never leaves the project page (SC-006).
export default function ProjectMembers({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const { user } = useSession();
  const { members, error, load, add, updateRole, remove } = useMembers();
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<MemberRole>("member");

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

  const confirmRemove = (target: string) => {
    if (window.confirm(t("members.remove_confirm", { username: target }))) {
      void remove(projectId, target);
    }
  };

  return (
    <section>
      <h2>{t("members.title")}</h2>
      <ul>
        {members.map((member) => (
          <li key={member.username}>
            <strong>{member.username}</strong> — {roleLabel(member.role)} (
            {member.granted_by ?? t("members.granted_by_system")},{" "}
            {new Date(member.granted_at).toLocaleDateString(i18n.language)})
            {isOwner && (
              <>
                {" "}
                <button
                  onClick={() =>
                    void updateRole(
                      projectId,
                      member.username,
                      member.role === "owner" ? "member" : "owner",
                    )
                  }
                >
                  {t(member.role === "owner" ? "members.revoke_owner" : "members.grant_owner")}
                </button>{" "}
                <button onClick={() => confirmRemove(member.username)}>
                  {t("members.remove")}
                </button>
              </>
            )}
          </li>
        ))}
      </ul>

      {isOwner && (
        <form onSubmit={(e) => void submit(e)}>
          <label>
            {t("members.add_label")}{" "}
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("auth.username")}
            />
          </label>{" "}
          <select value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
            <option value="member">{t("members.role_member")}</option>
            <option value="owner">{t("members.role_owner")}</option>
          </select>{" "}
          <button type="submit">{t("members.add_label")}</button>
        </form>
      )}

      {error && <p role="alert">{t(error)}</p>}
    </section>
  );
}
