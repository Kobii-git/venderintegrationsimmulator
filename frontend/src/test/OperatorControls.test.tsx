import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ConsoleTabs } from "../components/ConsoleTabs";
import { JsonViewer } from "../components/JsonViewer";

it("supports arrow, Home and End tab navigation with linked panels and native focus", async () => {
  function Tabs() {
    const [value, setValue] = useState("first");
    return <><ConsoleTabs id="test" label="Test views" value={value} onChange={setValue} tabs={[{ id: "first", label: "First" }, { id: "second", label: "Second" }]} />
      <section id="test-panel-first" role="tabpanel" aria-labelledby="test-tab-first" hidden={value !== "first"}>First view</section>
      <section id="test-panel-second" role="tabpanel" aria-labelledby="test-tab-second" hidden={value !== "second"}>Second view</section></>;
  }
  render(<Tabs />); const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "First" }));
  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("tab", { name: "Second" })).toHaveFocus();
  expect(screen.getByRole("tabpanel", { name: "Second" })).toBeVisible();
  await user.keyboard("{Home}"); expect(screen.getByRole("tab", { name: "First" })).toHaveFocus();
  await user.keyboard("{End}"); expect(screen.getByRole("tab", { name: "Second" })).toHaveFocus();
});

it("reports clipboard failure without losing the JSON evidence", async () => {
  const user = userEvent.setup();
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValueOnce(new Error("Unavailable"));
  render(<JsonViewer data={{ message: "retained" }} label="Evidence" />);
  await user.click(screen.getByRole("button", { name: "Copy JSON" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Clipboard unavailable");
  expect(screen.getByLabelText("Evidence")).toHaveTextContent('"message": "retained"');
});
