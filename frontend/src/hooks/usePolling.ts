import { useEffect, useRef } from "react";

export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  enabled: boolean,
): void {
  const saved = useRef(callback);

  useEffect(() => {
    saved.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) return undefined;

    const tick = () => {
      void saved.current();
    };

    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
}
