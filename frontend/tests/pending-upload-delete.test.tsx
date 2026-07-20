// Cancelling a pending upload: confirm dialog gates the API call, and the
// row disappears from the list on success (mirrors 005's delete flows).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import "../src/i18n";
import { api, PendingUpload } from "../src/api/client";
import PendingUploads from "../src/components/PendingUploads";
import { useUploads } from "../src/stores/uploads";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  useUploads.setState({ pendingByProject: {} });
});

const PROJECT_ID = "p1";

function pendingUpload(): PendingUpload {
  return {
    upload_session_id: "u1",
    declared_filename: "vuelo.laz",
    state: "active",
    received_bytes: 1000,
    declared_size_bytes: 10000,
  };
}

describe("PendingUploads delete action", () => {
  it("only calls deleteUpload after the confirm dialog is accepted, then removes the row", async () => {
    vi.spyOn(api, "listPendingUploads").mockResolvedValue([pendingUpload()]);
    const deleteSpy = vi.spyOn(api, "deleteUpload").mockResolvedValue({});

    render(<PendingUploads projectId={PROJECT_ID} />);

    await waitFor(() => expect(screen.getByText("vuelo.laz")).toBeTruthy());
    screen.getAllByText("Eliminar")[0].click();

    await waitFor(() => expect(screen.getByText(/¿Eliminar la subida pendiente/)).toBeTruthy());
    expect(deleteSpy).not.toHaveBeenCalled();

    const confirmButtons = screen.getAllByText("Eliminar");
    confirmButtons[confirmButtons.length - 1].click();

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(PROJECT_ID, "u1"));
    await waitFor(() => expect(screen.queryByText("vuelo.laz")).toBeNull());
  });

  it("renders nothing when there are no pending uploads", async () => {
    vi.spyOn(api, "listPendingUploads").mockResolvedValue([]);

    const { container } = render(<PendingUploads projectId={PROJECT_ID} />);

    await waitFor(() => expect(api.listPendingUploads).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });
});
