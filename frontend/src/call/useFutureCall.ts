import { useCallback, useEffect, useRef, useState } from "react";
import { FutureCall, INITIAL_SNAPSHOT, type CallSnapshot } from "./futureCall";

/** React wrapper around FutureCall: state for rendering, plus the AI voice level. */
export function useFutureCall(onAuthError: () => void) {
  const [snapshot, setSnapshot] = useState<CallSnapshot>(INITIAL_SNAPSHOT);
  const [level, setLevel] = useState(0);
  const callRef = useRef<FutureCall | null>(null);
  const onAuthErrorRef = useRef(onAuthError);

  useEffect(() => {
    onAuthErrorRef.current = onAuthError;
  }, [onAuthError]);

  // Sample the AI's voice level ~20 times a second for the particle ring.
  // Setting the same value (0 while silent) doesn't re-render.
  useEffect(() => {
    const id = window.setInterval(() => setLevel(callRef.current?.level() ?? 0), 50);
    return () => window.clearInterval(id);
  }, []);

  // Hang up if the app unmounts mid-call.
  useEffect(() => () => void callRef.current?.end(), []);

  /** Call from a click handler (browser audio rules). */
  const start = useCallback(() => {
    callRef.current?.end();
    const call = new FutureCall(setSnapshot, () => onAuthErrorRef.current());
    callRef.current = call;
    return call.prepare();
  }, []);

  const begin = useCallback(() => callRef.current?.begin(), []);
  const setMuted = useCallback((muted: boolean) => callRef.current?.setMuted(muted), []);
  const end = useCallback(() => callRef.current?.end() ?? 0, []);

  return { snapshot, level, start, begin, setMuted, end };
}
