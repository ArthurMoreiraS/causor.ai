"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function SetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // O link de convite/recuperação do Supabase abre uma sessão de recovery
    // (detectSessionInUrl=true no cliente). Só liberamos o form quando ela existe.
    supabase.auth.getSession().then(({ data }) => setReady(!!data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setReady(!!s));
    return () => sub.subscription.unsubscribe();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (updateError) {
      setError("Não foi possível definir a senha. O link pode ter expirado.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="authShell">
      <form className="authCard" onSubmit={handleSubmit}>
        <h1 className="authTitle">Causor</h1>
        <p className="authSub">Defina sua senha</p>
        {!ready && (
          <p className="authError">Abra esta página pelo link enviado ao seu e-mail.</p>
        )}
        <label className="authLabel">
          Nova senha
          <input
            className="authInput"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
            disabled={!ready}
          />
        </label>
        {error && <p className="authError">{error}</p>}
        <button className="authButton" type="submit" disabled={busy || !ready}>
          {busy ? "Salvando…" : "Salvar senha"}
        </button>
      </form>
    </div>
  );
}
