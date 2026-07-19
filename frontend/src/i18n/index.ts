// i18n bootstrap: Spanish primary, English secondary (constitution Principle IX).
// No user-visible string may live outside these catalogs.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./en/common.json";
import enErrors from "./en/errors.json";
import esCommon from "./es/common.json";
import esErrors from "./es/errors.json";

void i18n.use(initReactI18next).init({
  resources: {
    es: { translation: { ...esCommon, errors: esErrors } },
    en: { translation: { ...enCommon, errors: enErrors } },
  },
  lng: "es",
  fallbackLng: "es",
  interpolation: { escapeValue: false },
});

export default i18n;
