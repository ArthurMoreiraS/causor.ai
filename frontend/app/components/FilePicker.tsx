"use client";

import { useState, type ChangeEvent } from "react";
import { FileText, FileUp, X } from "lucide-react";

/** Tamanho legível em pt-BR: "820 KB", "4,2 MB". */
export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: value < 10 ? 1 : 0 })} ${units[unit]}`;
}

/** O navegador não aplica `accept` a arquivos arrastados; o filtro é refeito aqui. */
function accepts(accept: string | undefined, file: File) {
  if (!accept) return true;
  const name = file.name.toLowerCase();
  return accept.split(",").map(item => item.trim().toLowerCase()).filter(Boolean).some(rule =>
    rule.startsWith(".") ? name.endsWith(rule)
      : rule.endsWith("/*") ? file.type.startsWith(rule.slice(0, -1))
      : file.type === rule);
}

/**
 * Seleção de arquivos com área de soltar e lista do que foi escolhido.
 *
 * O <input type=file> cobre a área inteira (transparente): clique e arrastar
 * usam o seletor nativo, sem ref nem JS de drag-and-drop. A lista é o estado;
 * o valor do input é limpo a cada escolha, então escolher de novo acrescenta.
 */
export default function FilePicker({
  label, accept, multiple = false, disabled = false, files, onChange, hint, kind = "arquivos"
}: {
  label: string;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  files: File[];
  onChange: (files: File[]) => void;
  hint?: string;
  /** Como chamar os arquivos no texto da área: "PDFs", "imagens"... */
  kind?: string;
}) {
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState(0);

  function pick(event: ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(event.target.files || []);
    event.target.value = "";
    setDragging(false);
    const valid = chosen.filter(file => accepts(accept, file));
    setRejected(chosen.length - valid.length);
    if (!valid.length) return;
    if (!multiple) { onChange(valid.slice(0, 1)); return; }
    const known = new Set(files.map(file => `${file.name}:${file.size}`));
    onChange([...files, ...valid.filter(file => !known.has(`${file.name}:${file.size}`))]);
  }

  const total = files.reduce((sum, file) => sum + file.size, 0);
  return (
    <div className="filePicker">
      <span className="filePickerLabel">{label}</span>
      <label className={`fileDrop${dragging ? " dragging" : ""}${disabled ? " disabled" : ""}`}>
        <FileUp size={20} aria-hidden="true" />
        <span className="fileDropText">
          <strong>Arraste {multiple ? `os ${kind}` : `o ${kind}`} aqui ou <span className="fileDropLink">escolha no computador</span></strong>
          {hint ? <span>{hint}</span> : null}
        </span>
        <input
          type="file"
          aria-label={label}
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={pick}
          onDragEnter={() => setDragging(true)}
          onDragLeave={() => setDragging(false)}
          onDrop={() => setDragging(false)}
        />
      </label>
      {rejected ? <p role="alert" className="fileRejected">
        {rejected === 1 ? "1 arquivo ignorado" : `${rejected} arquivos ignorados`}: formato não aceito.
      </p> : null}
      {files.length ? <>
        <ul className="fileList" aria-label="Arquivos escolhidos">
          {files.map((file, index) => (
            <li key={`${file.name}:${file.size}:${index}`}>
              <FileText size={15} aria-hidden="true" />
              <span className="fileName" title={file.name}>{file.name}</span>
              <span className="fileSize">{formatFileSize(file.size)}</span>
              <button type="button" className="iconButton" disabled={disabled} aria-label={`Remover ${file.name}`}
                onClick={() => onChange(files.filter((_, position) => position !== index))}>
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
        <p className="fileSummary">
          {files.length === 1 ? "1 arquivo" : `${files.length} arquivos`} · {formatFileSize(total)}
        </p>
      </> : null}
    </div>
  );
}
