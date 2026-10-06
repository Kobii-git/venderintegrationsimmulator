import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { LogLabPage } from "../pages/LogLabPage";

vi.mock("../api/products", () => ({
  listProducts: vi.fn().mockResolvedValue([]),
  getProduct: vi.fn(),
}));
vi.mock("../api/client", () => ({
  get: vi.fn().mockResolvedValue([]),
  post: vi.fn(),
  request: vi.fn(),
  del: vi.fn(),
}));

afterEach(() => vi.unstubAllGlobals());

it("opens Log Lab and adds collectors and devices without secure-context randomUUID", async () => {
  // Browsers omit randomUUID on HTTP LAN origins while retaining getRandomValues.
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  render(
    <MemoryRouter>
      <LogLabPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("heading", { name: "Build a log lab" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add collector" }));
  expect(screen.getByLabelText("Collector 2 name")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add device" }));
  expect(screen.getByLabelText("Device 1 hostname")).toBeInTheDocument();
});
