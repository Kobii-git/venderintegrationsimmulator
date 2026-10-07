import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { generateRawLog, getProduct, listProducts } from "../api/products";
import { MemoryRouter } from "react-router-dom";
import { RawLogPage } from "../pages/RawLogPage";
import type {
  ProductDetail,
  ProductSummary,
  ScenarioRawPreviewResponse,
} from "../types/api";

vi.mock("../api/products", () => ({
  listProducts: vi.fn(),
  getProduct: vi.fn(),
  generateRawLog: vi.fn(),
}));

const product = {
  id: "upguard",
  display_name: "UpGuard",
  scenarios: [
    {
      id: "score-threshold",
      display_name: "Security Score Threshold",
      config_schema: { properties: {} },
    },
    {
      id: "data-leak",
      display_name: "Data Leak Detected",
      config_schema: {
        properties: {
          affected_domain: { type: "string", default: "example.com" },
        },
      },
    },
  ],
} as unknown as ProductDetail;
const raw: ScenarioRawPreviewResponse = {
  product_id: "upguard",
  scenario_id: "score-threshold",
  fidelity_mode: "vendor_accurate",
  content_type: "application/json",
  raw_log: '{"notification":{"type":"CustomerCSTARUnderThreshold"}}',
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listProducts).mockResolvedValue([product as ProductSummary]);
  vi.mocked(getProduct).mockResolvedValue(product);
  vi.mocked(generateRawLog).mockResolvedValue(raw);
});

it("generates the raw body without a destination and copies exactly the displayed sample", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><RawLogPage /></MemoryRouter>);
  const button = await screen.findByRole("button", {
    name: "Generate raw log",
  });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  expect(generateRawLog).toHaveBeenCalledWith("upguard", "score-threshold", {
    fidelity_mode: "vendor_accurate",
    scenario_overrides: {},
  });
  expect(await screen.findByLabelText("Raw log output")).toHaveValue(
    raw.raw_log,
  );
  await user.click(screen.getByRole("button", { name: "Copy raw log" }));
  expect(await navigator.clipboard.readText()).toBe(raw.raw_log);
});

it("discards old responses when the scenario changes and uses customized values", async () => {
  let finish!: (value: ScenarioRawPreviewResponse) => void;
  vi.mocked(generateRawLog).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const user = userEvent.setup();
  render(<MemoryRouter><RawLogPage /></MemoryRouter>);
  const button = screen.getByRole("button", { name: "Generate raw log" });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  await user.selectOptions(screen.getByLabelText("Scenario"), "data-leak");
  await act(async () => finish(raw));
  expect(screen.queryByLabelText("Raw log output")).not.toBeInTheDocument();
  await user.click(screen.getByText("Customize sample values"));
  await user.clear(screen.getByLabelText("affected_domain"));
  await user.type(screen.getByLabelText("affected_domain"), "custom.example");
  await user.selectOptions(
    screen.getByLabelText("Payload mode"),
    "troubleshooting",
  );
  await user.click(button);
  expect(generateRawLog).toHaveBeenLastCalledWith("upguard", "data-leak", {
    fidelity_mode: "troubleshooting",
    scenario_overrides: { affected_domain: "custom.example" },
  });
});

it("shows errors and removes outdated output when configuration changes", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><RawLogPage /></MemoryRouter>);
  const button = screen.getByRole("button", { name: "Generate raw log" });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  await screen.findByLabelText("Raw log output");
  await user.selectOptions(
    screen.getByLabelText("Payload mode"),
    "troubleshooting",
  );
  expect(screen.queryByLabelText("Raw log output")).not.toBeInTheDocument();
  vi.mocked(generateRawLog).mockRejectedValueOnce(
    new Error("Generation failed"),
  );
  await user.click(button);
  expect(await screen.findByText("Generation failed")).toBeInTheDocument();
});
