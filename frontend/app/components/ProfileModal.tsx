"use client";

import { LogOut, X } from "lucide-react";
import { useAuth } from "../AuthProvider";
import { Modal } from "./ui";

export default function ProfileModal({
  onClose,
  onSignOut
}: {
  onClose: () => void;
  onSignOut: () => void | Promise<void>;
}) {
  const { user } = useAuth();
  const email = user?.email ?? "";
  const initials = email ? email.slice(0, 2).toUpperCase() : "··";

  return (
    <Modal onClose={onClose} labelledBy="profileModalTitle" className="settingsCard">
        <header className="settingsHeader">
          <h3 id="profileModalTitle">Conta</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="profileCard">
          <div className="avatar large">{initials}</div>
          <div>
            <strong>{email || "Sessão ativa"}</strong>
            <span>Você está autenticado via Supabase.</span>
          </div>
        </div>
        <div className="settingsFooter">
          <button className="toolbarButton" onClick={() => onSignOut()}>
            <LogOut size={14} />
            Sair
          </button>
        </div>
    </Modal>
  );
}
