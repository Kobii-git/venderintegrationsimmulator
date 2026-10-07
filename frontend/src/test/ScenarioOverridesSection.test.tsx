import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ScenarioOverridesSection } from "../components/ScenarioOverridesSection";

it("hides ineffective legacy controls while retaining their stored overrides", async () => {
  const changed = vi.fn();
  render(<ScenarioOverridesSection scenarios={[{
    id: "waf-block", display_name: "WAF Block", description: null,
    default_transport: "cloudflare_logpush",
    config_schema: { properties: {
      src: { type: "string", default: "198.51.100.20" },
      action: { type: "string", default: "allow", hidden: true, deprecated: true },
    } },
  }]} selectedIds={["waf-block"]} value={{ "waf-block": { action: "legacy" } }} onChange={changed} />);
  expect(screen.queryByLabelText("action")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("src"), "x");
  expect(changed).toHaveBeenLastCalledWith({ "waf-block": { action: "legacy", src: "198.51.100.20x" } });
});
