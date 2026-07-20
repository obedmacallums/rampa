// T025: OptionPicker behavior contract — required options locked on, defaults
// pre-checked, prerequisite cascade in both directions (FR-006, R7).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import "../src/i18n";
import { ProcessingOption } from "../src/api/client";
import OptionPicker from "../src/components/OptionPicker";

afterEach(cleanup);

const REQUIRED_ONLY: ProcessingOption[] = [
  {
    id: "elevation",
    label_key: "options.elevation.label",
    description_key: "options.elevation.description",
    target_view: "map2d",
    required: true,
    default_selected: true,
    prerequisites: [],
  },
];

const CASCADE: ProcessingOption[] = [
  {
    id: "base",
    label_key: "options.elevation.label",
    description_key: "options.elevation.description",
    target_view: "map2d",
    required: false,
    default_selected: false,
    prerequisites: [],
  },
  {
    id: "dependent",
    label_key: "options.hillshade.label",
    description_key: "options.hillshade.description",
    target_view: "map2d",
    required: false,
    default_selected: false,
    prerequisites: ["base"],
  },
];

function Harness({ options, initial }: { options: ProcessingOption[]; initial: string[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initial));
  return <OptionPicker options={options} selected={selected} onChange={setSelected} />;
}

describe("OptionPicker", () => {
  it("required options render checked and disabled", () => {
    render(<Harness options={REQUIRED_ONLY} initial={["elevation"]} />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    expect(checkbox.disabled).toBe(true);
  });

  it("clicking a required (disabled) option has no effect", () => {
    render(<Harness options={REQUIRED_ONLY} initial={["elevation"]} />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
  });

  it("defaults arrive pre-checked", () => {
    render(<Harness options={CASCADE} initial={["base", "dependent"]} />);
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes.every((box) => box.checked)).toBe(true);
  });

  it("checking a dependent auto-checks its prerequisite", () => {
    render(<Harness options={CASCADE} initial={[]} />);
    const [baseBox, dependentBox] = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(baseBox.checked).toBe(false);
    expect(dependentBox.checked).toBe(false);

    fireEvent.click(dependentBox);

    expect(dependentBox.checked).toBe(true);
    expect(baseBox.checked).toBe(true);
  });

  it("unchecking a prerequisite unchecks its dependents", () => {
    render(<Harness options={CASCADE} initial={["base", "dependent"]} />);
    const [baseBox, dependentBox] = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(baseBox.checked).toBe(true);
    expect(dependentBox.checked).toBe(true);

    fireEvent.click(baseBox);

    expect(baseBox.checked).toBe(false);
    expect(dependentBox.checked).toBe(false);
  });
});
