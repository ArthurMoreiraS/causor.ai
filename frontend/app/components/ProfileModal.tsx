"use client";

import { useEffect, useState } from "react";
import { LogOut, Settings, X } from "lucide-react";
import { carregarPerfilOperacional, type OperationalProfile } from "@/lib/api";
import { PAPEL_LABEL, usePermissoes } from "@/lib/permissoes";
import { useAuth } from "../AuthProvider";
import { Modal, Skeleton } from "./ui";

function iniciais(nome: string, email: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (partes.length >= 2) return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return email ? email.slice(0, 2).toUpperCase() : "··";
}

export default function ProfileModal({
  onClose,
  onSignOut,
  onOpenSettings
}: {
  onClose: () => void;
  onSignOut: () => void | Promise<void>;
  onOpenSettings?: () => void;
}) {
  const { user } = useAuth();
  const { me } = usePermissoes(Boolean(user));
  const [profile, setProfile] = useState<OperationalProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    carregarPerfilOperacional()
      .then((value) => { if (active) setProfile(value); })
      .catch(() => undefined)
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const email = profile?.usuario.email ?? user?.email ?? "";
  const nome = profile?.usuario.nome ?? "";
  const oab = profile?.usuario.oab
    ? `${profile.usuario.oab}${profile.usuario.oab_uf ? `/${profile.usuario.oab_uf}` : ""}`
    : "Não informada";

  return (
    <Modal onClose={onClose} labelledBy="profileModalTitle" className="infoCard narrow">
      <header className="settingsHeader">
        <h3 id="profileModalTitle">Conta</h3>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="infoBody">
        <div className="profileHeader">
          <div className="avatar large" aria-hidden="true">{iniciais(nome, email)}</div>
          <div className="infoRowText">
            <strong>{nome || email || "Sessão ativa"}</strong>
            {nome && email ? <span>{email}</span> : null}
          </div>
        </div>

        {loading ? (
          <Skeleton height={96} radius={8} />
        ) : profile ? (
          <dl className="profileFacts">
            <dt>Escritório</dt>
            <dd>{profile.escritorio.nome}</dd>
            <dt>Papel</dt>
            <dd>{me ? PAPEL_LABEL[me.papel] : "—"}</dd>
            <dt>OAB</dt>
            <dd>{oab}</dd>
          </dl>
        ) : (
          <small className="settingsHint">Não foi possível carregar os dados do escritório.</small>
        )}
      </div>

      <footer className="settingsFooter profileFooter">
        <button className="toolbarButton" onClick={() => onSignOut()}>
          <LogOut size={14} />
          Sair
        </button>
        {onOpenSettings ? (
          <button className="toolbarButton primary" onClick={onOpenSettings}>
            <Settings size={14} />
            Editar perfil
          </button>
        ) : null}
      </footer>
    </Modal>
  );
}
