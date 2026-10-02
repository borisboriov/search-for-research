import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileObserver } from "@/components/analytics-observer";
import { observeProfile } from "@/lib/analytics";
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("@/lib/analytics", () => ({ observeProfile: vi.fn(), whenVisible: (callback: () => void) => { callback(); return () => {}; } }));
beforeEach(() => vi.mocked(observeProfile).mockClear());
describe("client profile observer", () => {
  it("observes each author after navigation, not rerenders or unmounted prefetch", () => {
    expect(observeProfile).not.toHaveBeenCalled();
    const { rerender } = render(<ProfileObserver authorId="A1234" />);
    rerender(<ProfileObserver authorId="A1234" />);
    expect(observeProfile).toHaveBeenCalledTimes(1);
    rerender(<ProfileObserver authorId="A5678" />);
    expect(observeProfile).toHaveBeenCalledTimes(2);
    expect(observeProfile).toHaveBeenLastCalledWith("A5678");
  });
});
