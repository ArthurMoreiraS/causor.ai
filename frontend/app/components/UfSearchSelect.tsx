"use client";

import { useMemo } from "react";
import { BRASIL_UFS } from "@/lib/brasil-ufs";
import SearchSelect from "./SearchSelect";

export default function UfSearchSelect({
  disabled,
  name = "uf",
  value,
  onChange
}: {
  disabled?: boolean;
  name?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const options = useMemo(
    () =>
      BRASIL_UFS.map((uf) => ({
        value: uf.sigla,
        label: `${uf.sigla} - ${uf.nome}`,
        detail: uf.nome,
        searchText: uf.nome
      })),
    []
  );

  return (
    <SearchSelect
      disabled={disabled}
      emptyLabel="Nenhuma UF encontrada"
      name={name}
      options={options}
      value={value.toUpperCase()}
      onChange={onChange}
    />
  );
}
