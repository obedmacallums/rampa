import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useSession } from "../stores/session";

export default function LoginPage() {
  const { t } = useTranslation();
  const login = useSession((s) => s.login);
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setErrorKey(null);
    try {
      await login(username, password);
      navigate("/");
    } catch (error) {
      setErrorKey(error instanceof ApiError ? error.messageKey : "errors.invalid_request");
    }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "4rem auto", display: "grid", gap: 8 }}>
      <label>
        {t("auth.username")}
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
      </label>
      <label>
        {t("auth.password")}
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {errorKey && <p role="alert">{t(errorKey)}</p>}
      <button type="submit">{t("auth.login")}</button>
    </form>
  );
}
