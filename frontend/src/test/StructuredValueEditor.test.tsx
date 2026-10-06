import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredValueEditor } from "../components/StructuredValueEditor";

it("keeps a stored Logic App signature masked and prevents disabling sensitivity", () => {
  render(
    <StructuredValueEditor
      label="URL query parameters"
      value={[{ name: "sig", sensitive: true, has_value: true }]}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("URL query parameters value 1")).toHaveAttribute(
    "type",
    "password",
  );
  expect(screen.getByLabelText("URL query parameters value 1")).toHaveValue("");
  expect(screen.getByRole("checkbox", { name: "Sensitive" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Sensitive" })).toBeDisabled();
});
