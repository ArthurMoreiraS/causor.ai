"use client";

import { Filter, X } from "lucide-react";
import type { FilterState } from "@/lib/format";

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
  const RISCOS = [
    { value: "", label: "Todos" },
    { value: "vencido", label: "Vencido" },
    { value: "alto", label: "Alto" },
    { value: "medio", label: "Médio" },
    { value: "baixo", label: "Baixo" },
    { value: "cumprido", label: "Cumprido" }
  ];
  return (
    <div className="filterPanel" onClick={(e) => e.stopPropagation()}>
      <header>
        <strong>Filtros</strong>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={14} />
        </button>
      </header>
      <label>
        Tribunal
        <select
          value={filters.tribunal}
          onChange={(e) => onChange({ ...filters, tribunal: e.target.value })}
        >
          <option value="">Todos</option>
          {options.tribunais.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        Sistema
        <select
          value={filters.sistema}
          onChange={(e) => onChange({ ...filters, sistema: e.target.value })}
        >
          <option value="">Todos</option>
          {options.sistemas.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label>
        Risco
        <select
          value={filters.risco}
          onChange={(e) => onChange({ ...filters, risco: e.target.value })}
        >
          {RISCOS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
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
