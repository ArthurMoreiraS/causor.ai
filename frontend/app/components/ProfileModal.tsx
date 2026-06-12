"use client";

import { LogOut, X } from "lucide-react";

export default function ProfileModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Conta</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="profileCard">
          <div className="avatar large">AM</div>
          <div>
            <strong>Usuário do piloto</strong>
            <span>Conta de demonstração — autenticação chega numa fase futura.</span>
          </div>
        </div>
        <div className="settingsFooter">
          <button className="toolbarButton" disabled title="Disponível quando a autenticação for implementada">
            <LogOut size={14} />
            Sair (em breve)
          </button>
        </div>
      </div>
    </div>
  );
}
