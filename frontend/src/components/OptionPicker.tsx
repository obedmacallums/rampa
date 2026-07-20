// Reusable processing-options checklist (US1 upload + US3 "process more
// options" later). Mirrors the server-side closure (R2/R7): required options
// are locked on; checking a dependent visibly cascades to its prerequisites;
// unchecking a prerequisite cascades the uncheck to its dependents (FR-006).
import { useTranslation } from "react-i18next";

import { ProcessingOption } from "../api/client";

interface Props {
  options: ProcessingOption[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  // Additionally locked ids (e.g. already produced on this survey, US3):
  // rendered checked + disabled like a required option, but independent of
  // the registry's `required` flag.
  locked?: Set<string>;
}

export default function OptionPicker({ options, selected, onChange, locked }: Props) {
  const { t } = useTranslation();
  const byId = new Map(options.map((option) => [option.id, option]));
  const dependentsOf = (id: string) => options.filter((option) => option.prerequisites.includes(id));
  const isLocked = (option: ProcessingOption) => option.required || Boolean(locked?.has(option.id));

  const toggle = (option: ProcessingOption, checked: boolean) => {
    if (isLocked(option)) return;
    const next = new Set(selected);

    if (checked) {
      next.add(option.id);
      const stack = [...option.prerequisites];
      while (stack.length) {
        const id = stack.pop()!;
        if (!next.has(id)) {
          next.add(id);
          stack.push(...(byId.get(id)?.prerequisites ?? []));
        }
      }
    } else {
      next.delete(option.id);
      const stack = [option.id];
      while (stack.length) {
        const id = stack.pop()!;
        for (const dependent of dependentsOf(id)) {
          if (!isLocked(dependent) && next.has(dependent.id)) {
            next.delete(dependent.id);
            stack.push(dependent.id);
          }
        }
      }
    }
    onChange(next);
  };

  return (
    <fieldset className="grid gap-2 rounded-md border border-surface-2 p-3">
      <legend className="px-1 text-sm font-medium text-text-strong">
        {t("upload.options_heading")}
      </legend>
      <p className="text-xs text-text-muted">{t("upload.options_help")}</p>
      {options.map((option) => {
        const optionLocked = isLocked(option);
        const checked = optionLocked || selected.has(option.id);
        return (
          <label key={option.id} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={checked}
              disabled={optionLocked}
              onChange={(event) => toggle(option, event.target.checked)}
            />
            <span className="grid gap-0.5">
              <span className="flex items-center gap-2 font-medium text-text-strong">
                {t(option.label_key)}
                <span className="rounded-full border border-surface-2 px-1.5 py-0.5 text-[10px] uppercase text-text-muted">
                  {t(option.target_view === "map2d" ? "surveys.view_2d" : "surveys.view_3d")}
                </span>
              </span>
              <span className="text-xs text-text-muted">{t(option.description_key)}</span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
