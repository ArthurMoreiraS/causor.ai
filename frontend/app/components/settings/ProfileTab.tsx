"use client";

import { useCallback, useEffect, useState } from "react";
import {
  atualizarPerfilOperacional,
  carregarPerfilOperacional,
  OperationalProfile
} from "@/lib/api";
import { humanError } from "@/lib/errors";
import UfSearchSelect from "../UfSearchSelect";
import { useToast } from "../Toast";
import { LoadingButton, Skeleton } from "../ui";

// Dados do advogado/escritório e o papel timbrado que o PDF de protocolo usa.
// O timbrado é um subgrupo visual dentro da aba, não outro cartão solto: são
// os mesmos dados de identidade, gravados pelo mesmo botão.
export default function ProfileTab({
  offline,
  onOabChanged
}: {
  offline: boolean;
  onOabChanged: () => Promise<void>;
}) {
  const toast = useToast();
  const [profile, setProfile] = useState<OperationalProfile | null>(null);
  const [form, setForm] = useState({
    nomeUsuario: "",
    nomeEscritorio: "",
    cnpj: "",
    oab: "",
    oabUf: "SP"
  });
  const [timbrado, setTimbrado] = useState({
    cabecalho: "",
    rodape: "",
    logo: "", // base64 enviado no PATCH ("" remove)
    logoPreview: "", // data URL para o <img>
    logoChanged: false
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyProfile = useCallback((next: OperationalProfile) => {
    setProfile(next);
    setForm({
      nomeUsuario: next.usuario.nome,
      nomeEscritorio: next.escritorio.nome,
      cnpj: next.escritorio.cnpj ?? "",
      oab: next.usuario.oab ?? "",
      oabUf: next.usuario.oab_uf ?? "SP"
    });
    setTimbrado({
      cabecalho: next.escritorio.timbrado_cabecalho ?? "",
      rodape: next.escritorio.timbrado_rodape ?? "",
      logo: next.escritorio.timbrado_logo ?? "",
      logoPreview: next.escritorio.timbrado_logo
        ? `data:image/png;base64,${next.escritorio.timbrado_logo}`
        : "",
      logoChanged: false
    });
  }, []);

  const load = useCallback(async () => {
    if (offline) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      applyProfile(await carregarPerfilOperacional());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Não foi possível carregar o perfil do escritório"));
    } finally {
      setLoading(false);
    }
  }, [applyProfile, offline]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setSaving(true);
    try {
      const updated = await atualizarPerfilOperacional({
        nome_usuario: form.nomeUsuario.trim(),
        nome_escritorio: form.nomeEscritorio.trim(),
        cnpj: form.cnpj.trim() || null,
        oab: form.oab.trim() || null,
        oab_uf: form.oabUf.trim().toUpperCase() || null,
        timbrado_cabecalho: timbrado.cabecalho.trim(),
        timbrado_rodape: timbrado.rodape.trim(),
        ...(timbrado.logoChanged ? { timbrado_logo: timbrado.logo } : {})
      });
      applyProfile(updated);
      setError(null);
      await onOabChanged();
      toast({ kind: "success", title: "Perfil salvo" });
    } catch (err) {
      setError(humanError(err, "O perfil não foi salvo"));
    } finally {
      setSaving(false);
    }
  }

  function onLogoSelected(file: File | null) {
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) {
      setError("O logo precisa ser PNG ou JPEG.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("O logo precisa ter no máximo 2 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
      setTimbrado((t) => ({ ...t, logo: base64, logoPreview: dataUrl, logoChanged: true }));
      setError(null);
    };
    reader.readAsDataURL(file);
  }

  if (loading) {
    return (
      <div className="skeletonGroup" aria-hidden="true">
        <Skeleton height={38} radius={6} />
        <Skeleton height={38} radius={6} />
        <Skeleton height={38} radius={6} />
        <Skeleton height={72} radius={6} />
      </div>
    );
  }

  return (
    <>
      <section className="settingsSection">
        <div className="settingsSectionHead">
          <h4>Identificação</h4>
          <p>Aparece no cabeçalho das peças e identifica sua conta no Causor.</p>
        </div>

        <div className="settingsRow single">
          <label>
            Nome do usuário
            <input
              value={form.nomeUsuario}
              disabled={offline}
              onChange={(e) => setForm((f) => ({ ...f, nomeUsuario: e.target.value }))}
            />
          </label>
        </div>
        <div className="settingsRow duo">
          <label>
            Nome do escritório
            <input
              value={form.nomeEscritorio}
              disabled={offline}
              onChange={(e) => setForm((f) => ({ ...f, nomeEscritorio: e.target.value }))}
            />
          </label>
          <label>
            CNPJ
            <input
              value={form.cnpj}
              disabled={offline}
              placeholder="Opcional"
              onChange={(e) => setForm((f) => ({ ...f, cnpj: e.target.value }))}
            />
          </label>
        </div>
        <div className="settingsRow ufRow">
          <label>
            OAB do usuário
            <input
              value={form.oab}
              disabled={offline}
              placeholder="Número"
              onChange={(e) => setForm((f) => ({ ...f, oab: e.target.value }))}
            />
          </label>
          <label>
            UF
            <UfSearchSelect
              value={form.oabUf}
              disabled={offline}
              name="oab_uf"
              onChange={(uf) => setForm((f) => ({ ...f, oabUf: uf }))}
            />
          </label>
        </div>
      </section>

      <section className="settingsSection">
        <div className="settingsSectionHead">
          <h4>Papel timbrado</h4>
          <p>Usado no PDF que acompanha o protocolo. Uma linha aqui é uma linha no papel.</p>
        </div>

        <div className="settingsLogoRow">
          {timbrado.logoPreview ? (
            <span className="settingsLogoPreview">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={timbrado.logoPreview} alt="Logo do escritório" />
            </span>
          ) : (
            <span className="settingsLogoPreview blank" aria-hidden="true">
              Sem logo
            </span>
          )}
          <div className="settingsLogoActions">
            <label className="toolbarButton compact settingsFileButton">
              {timbrado.logoPreview ? "Trocar logo" : "Escolher logo"}
              <input
                type="file"
                accept="image/png,image/jpeg"
                disabled={offline}
                onChange={(e) => onLogoSelected(e.target.files?.[0] ?? null)}
              />
            </label>
            {timbrado.logoPreview ? (
              <button
                type="button"
                className="toolbarButton compact"
                disabled={offline}
                onClick={() =>
                  setTimbrado((t) => ({ ...t, logo: "", logoPreview: "", logoChanged: true }))
                }
              >
                Remover
              </button>
            ) : null}
            <small className="settingsHint">PNG ou JPEG, até 2 MB.</small>
          </div>
        </div>

        <div className="settingsRow single">
          <label>
            Cabeçalho
            <textarea
              rows={4}
              value={timbrado.cabecalho}
              disabled={offline}
              placeholder="Endereço, telefone, contato"
              onChange={(e) => setTimbrado((t) => ({ ...t, cabecalho: e.target.value }))}
            />
          </label>
        </div>
        <div className="settingsRow single">
          <label>
            Rodapé
            <textarea
              rows={3}
              value={timbrado.rodape}
              disabled={offline}
              placeholder="OABs, site"
              onChange={(e) => setTimbrado((t) => ({ ...t, rodape: e.target.value }))}
            />
          </label>
        </div>
      </section>

      <div className="settingsSectionFoot">
        <LoadingButton
          className="toolbarButton primary"
          loading={saving}
          disabled={offline || !form.nomeUsuario.trim() || !form.nomeEscritorio.trim()}
          onClick={() => void save()}
        >
          Salvar perfil
        </LoadingButton>
        {profile ? (
          <small className="settingsHint">Conta conectada: {profile.usuario.email}</small>
        ) : null}
      </div>

      {error ? (
        <small className="settingsHint vaultError" role="alert">
          {error}
        </small>
      ) : null}
    </>
  );
}
