import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useSession } from "../stores/session";
import Alert from "../ui/Alert";
import Button from "../ui/Button";
import Field from "../ui/Field";

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
    <main className="mx-auto max-w-sm px-6 pt-24">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-text-strong">
          {t("app.brand")}
          <span className="text-accent">.</span>
        </h1>
        <p className="mt-2 text-sm text-text-muted">{t("app.title")}</p>
      </div>
      <form
        onSubmit={submit}
        className="grid gap-4 rounded-lg border border-surface-2 bg-surface-1 p-6"
      >
        <Field label={t("auth.username")}>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </Field>
        <Field label={t("auth.password")}>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {errorKey && <Alert>{t(errorKey)}</Alert>}
        <Button type="submit">{t("auth.login")}</Button>
      </form>
    </main>
  );
}
