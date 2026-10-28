import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageProvider, tr, translate } from "@/i18n";
import LanguageToggle from "@/components/ui/LanguageToggle";

describe("English and Persian interface", () => {
  beforeEach(() => {
    window.localStorage.removeItem("study-agent:locale");
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
  });
  afterEach(() => {
    window.localStorage.removeItem("study-agent:locale");
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
  });

  it("translates static labels and preserves unknown content", () => {
    expect(translate("Library", "fa")).toBe("کتابخانه");
    expect(translate("Library", "en")).toBe("Library");
    expect(translate("bio.pdf", "fa")).toBe("bio.pdf");
    expect(tr("Quiz")).toBe("Quiz");
  });

  it("switches document direction, language and persists the choice", async () => {
    render(<LanguageProvider><LanguageToggle /></LanguageProvider>);
    expect(screen.getByRole("button", { name: "تغییر زبان به فارسی" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "تغییر زبان به فارسی" }));
    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute("lang", "fa");
      expect(document.documentElement).toHaveAttribute("dir", "rtl");
    });
    expect(window.localStorage.getItem("study-agent:locale")).toBe("fa");
    expect(screen.getByRole("button", { name: "Switch language to English" })).toBeInTheDocument();
    expect(tr("Quiz")).toBe("آزمون");
    await userEvent.click(screen.getByRole("button", { name: "Switch language to English" }));
    await waitFor(() => expect(document.documentElement).toHaveAttribute("dir", "ltr"));
    expect(tr("Quiz")).toBe("Quiz");
  });
});
