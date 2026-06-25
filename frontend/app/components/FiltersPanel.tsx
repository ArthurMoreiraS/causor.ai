"use client";

import { Filter, X } from "lucide-react";
import { useEffect } from "react";
import type { FilterState } from "@/lib/format";
import SearchSelect from "./SearchSelect";

export default function FiltersPanel({
  filters,
  options,
  onChange,
  onClear,
  onClose
}: {
  filters: FilterState;
  options: { tribunais: string[]; sistemas: string[] };
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const RISCOS = [
    { value: "", label: "Todos" },
    { value: "vencido", label: "Vencido" },
    { value: "alto", label: "Alto" },
    { value: "medio", label: "Médio" },
    { value: "baixo", label: "Baixo" },
    { value: "cumprido", label: "Cumprido" }
  ];
  const tribunalOptions = [
    { value: "", label: "Todos" },
    ...options.tribunais.map((tribunal) => ({ value: tribunal, label: tribunal }))
  ];
  const sistemaOptions = [
    { value: "", label: "Todos" },
    ...options.sistemas.map((sistema) => ({ value: sistema, label: sistema }))
  ];

  return (
    <div
      className="filterPanel"
      role="dialog"
      aria-label="Filtros"
      onClick={(e) => e.stopPropagation()}
    >
      <header>
        <strong>Filtros</strong>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={14} />
        </button>
      </header>
      <label>
        Tribunal
        <SearchSelect
          value={filters.tribunal}
          options={tribunalOptions}
          onChange={(tribunal) => onChange({ ...filters, tribunal })}
        />
      </label>
      <label>
        Sistema
        <SearchSelect
          value={filters.sistema}
          options={sistemaOptions}
          onChange={(sistema) => onChange({ ...filters, sistema })}
        />
      </label>
      <label>
        Risco
        <SearchSelect
          value={filters.risco}
          options={RISCOS}
          onChange={(risco) => onChange({ ...filters, risco })}
        />
      </label>
      <footer>
        <button className="toolbarButton compact" onClick={onClear}>
          <Filter size={14} />
          Limpar
        </button>
        <button className="toolbarButton primary" onClick={onClose}>
          Aplicar
        </button>
      </footer>
    </div>
  );
}
