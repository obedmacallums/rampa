// Every backend failure/API error code must have a message in BOTH locales
// (SC-003 + Principle IX): a missing key would surface a raw code to the user.
import { describe, expect, it } from "vitest";

import en from "../src/i18n/en/errors.json";
import es from "../src/i18n/es/errors.json";

const PIPELINE_CODES = ["unsupported_format", "unreadable_file", "missing_crs", "internal_error"];
const API_CODES = [
  "file_too_large",
  "unsupported_extension",
  "invalid_capture_date",
  "name_taken",
  "invalid_crs",
  "invalid_credentials",
  "not_authenticated",
  "not_ready",
  "not_retriable",
];

describe("error catalogs", () => {
  it.each([...PIPELINE_CODES, ...API_CODES])("has es + en message for %s", (code) => {
    expect(es[code as keyof typeof es], `es missing ${code}`).toBeTruthy();
    expect(en[code as keyof typeof en], `en missing ${code}`).toBeTruthy();
  });

  it("both locales cover the same keys", () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
  });
});
