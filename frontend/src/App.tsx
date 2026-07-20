import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import ProjectsPage from "./pages/ProjectsPage";
import RecentlyDeletedPage from "./pages/RecentlyDeletedPage";
import { useSession } from "./stores/session";
import Button from "./ui/Button";
import LanguageSwitcher from "./ui/LanguageSwitcher";

export default function App() {
  const { t } = useTranslation();
  const { user, ready, bootstrap, logout } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  if (!ready) return null;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-surface-2 bg-surface-1">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-6">
          <Link
            to="/"
            className="text-lg font-semibold tracking-tight text-text-strong"
            title={t("app.title")}
          >
            {t("app.brand")}
            <span className="text-accent">.</span>
          </Link>
          {user && (
            <nav className="flex items-center gap-4 text-sm">
              <Link to="/" className="text-text-muted transition-colors hover:text-text-strong">
                {t("nav.projects")}
              </Link>
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3">
            <LanguageSwitcher />
            {user && (
              <>
                <span className="text-sm text-text-muted">{user.username}</span>
                <Button
                  variant="secondary"
                  onClick={() => {
                    void logout().then(() => navigate("/login"));
                  }}
                >
                  {t("auth.logout")}
                </Button>
              </>
            )}
          </div>
        </div>
      </header>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={user ? <ProjectsPage /> : <Navigate to="/login" />} />
        <Route
          path="/projects/:projectId"
          element={user ? <ProjectDetailPage /> : <Navigate to="/login" />}
        />
        <Route
          path="/deleted"
          element={user ? <RecentlyDeletedPage /> : <Navigate to="/login" />}
        />
      </Routes>
    </div>
  );
}
