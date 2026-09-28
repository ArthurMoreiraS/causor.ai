"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { consultarCapturaOab, iniciarCapturaOab, JobExecucao, listarCapturasOab } from "@/lib/api";
import { capturePhase, sameCapture, type CapturePhase } from "@/lib/oab-capture";
import { humanError } from "@/lib/errors";

export function useOabCapture(accountId: string | null, onRegistered: () => void, onTerminal: (job: JobExecucao) => void) {
  const [job, setJob] = useState<JobExecucao | null>(null);
  const [phase, setPhase] = useState<CapturePhase>("idle");
  const [trackingError, setTrackingError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const callbacks = useRef({ onRegistered, onTerminal });
  callbacks.current = { onRegistered, onTerminal };
  const lastTerminal = useRef<string | null>(null);
  const inFlight = useRef<symbol | null>(null);
  const generation = useRef(0);
  const mounted = useRef(false);
  const currentAccount = useRef(accountId);
  currentAccount.current = accountId;
  const isCurrent = useCallback((epoch: number) => mounted.current && currentAccount.current === accountId && generation.current === epoch, [accountId]);
  const begin = useCallback(() => {
    if (inFlight.current) return null;
    const token = Symbol();
    inFlight.current = token;
    return { token, epoch: generation.current };
  }, []);
  const end = useCallback((token: symbol) => { if (inFlight.current === token) inFlight.current = null; }, []);

  const accept = useCallback((next: JobExecucao, announce = true) => {
    setJob(next);
    const nextPhase = capturePhase(next);
    setPhase(nextPhase);
    setTrackingError(null);
    setCheckedAt(Date.now());
    if (announce && (nextPhase === "completed" || nextPhase === "failed")) {
      const identity = `${next.id}:${nextPhase}`;
      if (lastTerminal.current !== identity) {
        lastTerminal.current = identity;
        callbacks.current.onTerminal(next);
      }
    }
  }, []);

  const attemptKey = accountId ? `causor:capture-attempt:${accountId}` : null;
  const readAttempt = useCallback(() => {
    if (!attemptKey) return null;
    try { return JSON.parse(window.sessionStorage.getItem(attemptKey) || "null") as { oab: string; uf: string; id: string } | null; }
    catch { return null; }
  }, [attemptKey]);
  const clearAttempt = useCallback(() => {
    if (attemptKey) { try { window.sessionStorage.removeItem(attemptKey); } catch { /* unavailable storage */ } }
  }, [attemptKey]);
  const matchesAttempt = useCallback((item: JobExecucao, attempt: { oab: string; uf: string; id: string }) =>
    sameCapture(item, attempt.oab, attempt.uf) &&
    (item.payload?.request_id === attempt.id ||
      (Array.isArray(item.payload?.request_ids) && item.payload.request_ids.includes(attempt.id))), []);

  const recover = useCallback(async (target?: { oab: string; uf: string }) => {
    const run = begin();
    if (!run) return undefined;
    try {
      const jobs = await listarCapturasOab();
      if (!isCurrent(run.epoch)) return undefined;
      const attempt = readAttempt();
      const pending = attempt && (!target || (attempt.oab === target.oab && attempt.uf === target.uf)) ? attempt : null;
      let found = pending ? jobs.find((item) => matchesAttempt(item, pending)) : undefined;
      if (!found && pending) {
        // Same key reconciles a lost response even after the job leaves the list.
        found = await iniciarCapturaOab(pending.oab, pending.uf, pending.id);
      }
      if (!found) found = target
        ? jobs.find((item) => sameCapture(item, target.oab, target.uf) && ["queued", "running"].includes(item.status))
        : jobs.find((item) => ["queued", "running"].includes(item.status)) ?? jobs[0];
      if (!isCurrent(run.epoch)) return undefined;
      if (found) { accept(found, Boolean(target || pending)); if (pending) clearAttempt(); }
      else if (!target) { setJob(null); setPhase("idle"); setTrackingError(null); }
      return found ?? null;
    } catch (err) {
      if (!isCurrent(run.epoch)) return undefined;
      setPhase("lost");
      setTrackingError(humanError(err, "Não foi possível consultar a captura"));
      return undefined;
    } finally {
      end(run.token);
    }
  }, [accept, readAttempt, clearAttempt, isCurrent, begin, end, matchesAttempt]);

  const submit = useCallback(async (oab: string, uf: string) => {
    const epoch = generation.current;
    oab = oab.replace(/[\s.\-/]/g, "").toUpperCase();
    uf = uf.trim().toUpperCase();
    if (inFlight.current) return;
    if (job && sameCapture(job, oab, uf) && ["queued", "running"].includes(job.status)) return;
    setJob(null);
    setPhase("sending");
    setTrackingError(null);
    // Preserve an uncertain POST for another OAB before recording a new key.
    const pending = readAttempt();
    if (pending && (pending.oab !== oab || pending.uf !== uf)) {
      const previous = await recover();
      if (!isCurrent(epoch) || previous === undefined) return;
      if (readAttempt()) return;
    }
    // First reconcile an uncertain POST; the API also deduplicates.
    const existing = await recover({ oab, uf });
    if (!isCurrent(epoch)) return;
    if (existing || existing === undefined || inFlight.current) {
      if (existing) callbacks.current.onRegistered();
      return;
    }
    const prior = readAttempt();
    const requestId = prior?.oab === oab && prior.uf === uf ? prior.id : crypto.randomUUID();
    if (attemptKey) {
      try { window.sessionStorage.setItem(attemptKey, JSON.stringify({ oab, uf, id: requestId })); }
      catch { /* server deduplication still protects active jobs */ }
    }
    const run = begin();
    if (!run) return;
    try {
      const created = await iniciarCapturaOab(oab, uf, requestId);
      if (!isCurrent(run.epoch)) return;
      accept(created);
      clearAttempt();
      callbacks.current.onRegistered();
    } catch (err) {
      if (!isCurrent(run.epoch)) return;
      setPhase("lost");
      setTrackingError(humanError(err, "Não foi possível confirmar o envio da captura"));
    } finally {
      end(run.token);
    }
  }, [accept, recover, job, attemptKey, readAttempt, clearAttempt, isCurrent, begin, end]);

  const check = useCallback(async () => {
    if (inFlight.current) return;
    if (readAttempt() || !job) { await recover(); return; }
    const run = begin();
    if (!run) return;
    try {
      const updated = await consultarCapturaOab(job.id);
      if (isCurrent(run.epoch)) accept(updated);
    } catch (err) {
      if (!isCurrent(run.epoch)) return;
      setPhase("lost");
      setTrackingError(humanError(err, "Não foi possível acompanhar a captura"));
    } finally {
      end(run.token);
    }
  }, [accept, job, recover, readAttempt, isCurrent, begin, end]);

  useEffect(() => {
    generation.current += 1;
    mounted.current = true;
    setJob(null); setPhase("idle"); setTrackingError(null);
    inFlight.current = null;
    lastTerminal.current = null;
    return () => { mounted.current = false; generation.current += 1; inFlight.current = null; };
  }, [accountId]);

  useEffect(() => { if (accountId) void recover(); }, [accountId, recover]);
  useEffect(() => {
    if (phase !== "queued" && phase !== "running") return;
    const id = window.setInterval(() => void check(), 5000);
    return () => window.clearInterval(id);
  }, [check, phase]);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 5000);
    return () => window.clearInterval(id);
  }, []);

  return { job, phase, trackingError, checkedAt, now, submit, check, recover };
}
