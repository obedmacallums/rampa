// ConfirmDialog behavior contract (specs/003-ui-foundation/contracts/ui-components.md):
// native <dialog> via showModal, Esc cancels, confirm/cancel callbacks fire.
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ConfirmDialog from "../src/ui/ConfirmDialog";

// jsdom does not implement showModal/close; stub them tracking open state.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

afterEach(cleanup);

const baseProps = {
  message: "Remove ana?",
  confirmLabel: "Remove",
  cancelLabel: "Cancel",
};

describe("ConfirmDialog", () => {
  it("opens via showModal when open=true", () => {
    const { container } = render(
      <ConfirmDialog {...baseProps} open onConfirm={() => {}} onCancel={() => {}} />,
    );
    const dialog = container.querySelector("dialog");
    expect(dialog?.open).toBe(true);
    expect(dialog?.textContent).toContain("Remove ana?");
  });

  it("stays closed when open=false", () => {
    const { container } = render(
      <ConfirmDialog {...baseProps} open={false} onConfirm={() => {}} onCancel={() => {}} />,
    );
    expect(container.querySelector("dialog")?.open).toBeFalsy();
  });

  it("fires onConfirm from the confirm button", () => {
    const onConfirm = vi.fn();
    const { getByText } = render(
      <ConfirmDialog {...baseProps} open onConfirm={onConfirm} onCancel={() => {}} />,
    );
    getByText("Remove").click();
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("fires onCancel from the cancel button", () => {
    const onCancel = vi.fn();
    const { getByText } = render(
      <ConfirmDialog {...baseProps} open onConfirm={() => {}} onCancel={onCancel} />,
    );
    getByText("Cancel").click();
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("fires onCancel when the dialog closes natively (Esc)", () => {
    const onCancel = vi.fn();
    const { container } = render(
      <ConfirmDialog {...baseProps} open onConfirm={() => {}} onCancel={onCancel} />,
    );
    // Native Esc handling triggers "cancel" then closes the dialog.
    const dialog = container.querySelector("dialog");
    dialog?.dispatchEvent(new Event("cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
