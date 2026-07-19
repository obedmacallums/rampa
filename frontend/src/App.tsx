import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import ProjectsPage from "./pages/ProjectsPage";
import { useSession } from "./stores/session";

export default function App() {
  const { t } = useTranslation();
  const { user, ready, bootstrap, logout } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  if (!ready) return null;

  return (
    <div>
      <header style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 1rem" }}>
        <strong>{t("app.title")}</strong>
        {user && (
          <button
            onClick={() => {
              void logout().then(() => navigate("/login"));
            }}
          >
            {t("auth.logout")}
          </button>
        )}
      </header>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={user ? <ProjectsPage /> : <Navigate to="/login" />} />
        <Route
          path="/projects/:projectId"
          element={user ? <ProjectDetailPage /> : <Navigate to="/login" />}
        />
      </Routes>
    </div>
  );
}
