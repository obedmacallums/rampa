import { useTranslation } from "react-i18next";

const LANGUAGES = ["es", "en"] as const;

export default function LanguageSwitcher() {
  const { t, i18n } = useTranslation();

  const select = (lang: (typeof LANGUAGES)[number]) => {
    void i18n.changeLanguage(lang);
    localStorage.setItem("rampa.lang", lang);
  };

  return (
    <div
      role="group"
      aria-label={t("common.language")}
      className="flex overflow-hidden rounded-md border border-surface-2 text-xs font-medium"
    >
      {LANGUAGES.map((lang) => {
        const active = i18n.language === lang;
        return (
          <button
            key={lang}
            type="button"
            aria-pressed={active}
            onClick={() => select(lang)}
            className={
              active
                ? "bg-accent px-2 py-1 text-on-accent"
                : "px-2 py-1 text-text-muted transition-colors hover:bg-surface-2"
            }
          >
            {lang.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
