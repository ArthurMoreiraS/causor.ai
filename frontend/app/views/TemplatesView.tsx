"use client";

import { FilePlus2, Loader2, Save, ToggleLeft, ToggleRight } from "lucide-react";
import { useEffect, useState } from "react";
import {
  atualizarTemplate,
  criarTemplate,
  listarTemplates,
  TemplatePeticao
} from "@/lib/api";
import { Empty } from "../components/ui";

type FormState = {
  id: number | null;
  nome: string;
  tipo: string;
  area: string;
  conteudo: string;
};

const EMPTY_FORM: FormState = { id: null, nome: "", tipo: "", area: "", conteudo: "" };

export default function TemplatesView({ offline }: { offline: boolean }) {
  const [templates, setTemplates] = useState<TemplatePeticao[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      setTemplates(await listarTemplates());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar templates");
    }
  }

  useEffect(() => {
    if (!offline) void reload();
  }, [offline]);

  async function save() {
    if (!form.nome.trim() || !form.tipo.trim() || form.conteudo.trim().length < 10) {
      setError("Preencha nome, tipo e um conteúdo com pelo menos 10 caracteres.");
      return;
    }
    setBusy("save");
    setError(null);
    try {
      if (form.id === null) {
        await criarTemplate({
          nome: form.nome.trim(),
          tipo: form.tipo.trim(),
          area: form.area.trim() || null,
          conteudo: form.conteudo
        });
      } else {
        await atualizarTemplate(form.id, {
          nome: form.nome.trim(),
          tipo: form.tipo.trim(),
          area: form.area.trim() || null,
          conteudo: form.conteudo
        });
      }
      setForm(EMPTY_FORM);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar o template");
    } finally {
      setBusy(null);
    }
  }

  async function toggleAtivo(template: TemplatePeticao) {
    setBusy(`toggle-${template.id}`);
    try {
      await atualizarTemplate(template.id, { ativo: !template.ativo });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar o template");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="templatesSurface">
      <div className="templatesColumn">
        <div className="templatesHead">
          <strong>Modelos do escritório</strong>
          <button
            className="toolbarButton compact"
            onClick={() => setForm(EMPTY_FORM)}
            disabled={offline}
          >
            <FilePlus2 size={14} />
            Novo template
          </button>
        </div>
        {error ? <div className="notice">{error}</div> : null}
        <div className="templatesList">
          {templates.map((template) => (
            <article
              className={`templateCard clickable ${form.id === template.id ? "selected" : ""}`}
              key={template.id}
              onClick={() =>
                setForm({
                  id: template.id,
                  nome: template.nome,
                  tipo: template.tipo,
                  area: template.area ?? "",
                  conteudo: template.conteudo
                })
              }
            >
              <header>
                <div>
                  <strong>{template.nome}</strong>
                  <span>
                    {template.tipo}
                    {template.area ? ` · ${template.area}` : ""}
                  </span>
                </div>
                <button
                  className="iconButton"
                  title={template.ativo ? "Desativar" : "Ativar"}
                  disabled={offline || busy === `toggle-${template.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    void toggleAtivo(template);
                  }}
                >
                  {busy === `toggle-${template.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : template.ativo ? (
                    <ToggleRight size={16} />
                  ) : (
                    <ToggleLeft size={16} />
                  )}
                </button>
              </header>
              <span className={`pill ${template.ativo ? "aprovada" : "rascunho"}`}>
                {template.ativo ? "Ativo" : "Inativo"}
              </span>
            </article>
          ))}
          {!templates.length ? (
            <Empty label="Nenhum template ainda — crie o primeiro modelo do escritório" />
          ) : null}
        </div>
      </div>

      <div className="templatesEditor">
        <strong>{form.id === null ? "Novo template" : "Editar template"}</strong>
        <span className="templatesHint">
          A IA continua decidindo tipo e prazo da peça; o template estrutura a redação da minuta.
        </span>
        <div className="templatesFields">
          <label>
            Nome
            <input
              value={form.nome}
              placeholder="Contestação cível padrão"
              onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
            />
          </label>
          <label>
            Tipo de peça
            <input
              value={form.tipo}
              placeholder="Contestação"
              onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))}
            />
          </label>
          <label>
            Área (opcional)
            <input
              value={form.area}
              placeholder="Cível"
              onChange={(e) => setForm((f) => ({ ...f, area: e.target.value }))}
            />
          </label>
        </div>
        <label className="templatesContent">
          Conteúdo
          <textarea
            value={form.conteudo}
            rows={10}
            placeholder={"EXCELENTÍSSIMO SENHOR DOUTOR JUIZ...\n\n{{cliente}}, nos autos..."}
            onChange={(e) => setForm((f) => ({ ...f, conteudo: e.target.value }))}
          />
        </label>
        {form.conteudo ? (
          <div className="templatesPreview">
            <span>Preview</span>
            <pre>{form.conteudo}</pre>
          </div>
        ) : null}
        <div className="templatesActions">
          <button className="toolbarButton primary" disabled={offline || busy === "save"} onClick={() => void save()}>
            {busy === "save" ? <Loader2 className="spin" size={14} /> : <Save size={14} />}
            {form.id === null ? "Criar template" : "Salvar alterações"}
          </button>
        </div>
      </div>
    </section>
  );
}
