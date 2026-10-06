"use client";

import { useEffect, useRef } from "react";
import { consultarAnalisesPrazo, type Intimacao, type IntimacaoAnalysis } from "@/lib/api";

/** Poll only pending states; reload the full dashboard once the batch finishes. */
export function useDeadlineAnalysis(
  userId: string | undefined,
  notices: Intimacao[],
  onStates: (states: IntimacaoAnalysis[], expected: Map<number, number | undefined>) => void,
  onCompleted: () => Promise<boolean>,
) {
  const callbacks = useRef({ onStates, onCompleted });
  callbacks.current = { onStates, onCompleted };
  const inFlight = useRef(false);
  const key = JSON.stringify(notices.filter(item => item.prazo_analise?.status === "analisando")
    .map(item => [item.id, item.prazo_analise?.job_id]).sort((a, b) => a[0]! - b[0]!));

  useEffect(() => {
    const pending = JSON.parse(key) as [number, number | undefined][];
    if (!userId || !pending.length) return;
    const expected = new Map(pending.map(([id, job]) => [id, job ?? undefined]));
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = () => {
      clearTimeout(timer);
      if (active && !document.hidden) timer = setTimeout(() => void check(), 5000);
    };
    const check = async () => {
      if (!active || document.hidden) return;
      if (inFlight.current) { schedule(); return; }
      inFlight.current = true;
      let finished = false;
      try {
        const states = await consultarAnalisesPrazo([...expected.keys()]);
        if (!active || document.hidden) return;
        // A later retry can replace a job while this response is in transit.
        const matching = states.filter(item => !item.prazo_analise?.job_id ||
          item.prazo_analise.job_id === expected.get(item.id));
        if (matching.length !== states.length) {
          // A retry from another tab changed ownership; reconcile the snapshot.
          finished = await callbacks.current.onCompleted();
          return;
        }
        finished = !matching.some(item => item.prazo_analise?.status === "analisando");
        if (finished) {
          // Refresh includes new deadlines/metrics and removed notices. Keep the
          // polling state pending until refresh succeeds, so a failure retries.
          finished = await callbacks.current.onCompleted();
        } else {
          callbacks.current.onStates(matching, expected);
        }
      } catch {
        finished = false;
        // A transient failure preserves the visible state and retries later.
      } finally {
        inFlight.current = false;
        if (!finished) schedule();
      }
    };
    const visibilityChanged = () => {
      clearTimeout(timer);
      if (!document.hidden) void check();
    };
    document.addEventListener("visibilitychange", visibilityChanged);
    schedule();
    return () => {
      active = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }, [userId, key]);
}
