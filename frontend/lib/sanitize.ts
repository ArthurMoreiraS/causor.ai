"use client";

/**
 * Sanitiza HTML cru vindo de fontes externas (intimações DJEN/DataJud) para
 * renderização segura no cliente, SEM depender de libs externas.
 *
 * Estratégia: parse num container detached, remove tags/atributos perigosos e
 * mantém só uma whitelist de tags/atributos visuais. Previne XSS mesmo quando
 * o teor vem com <script>, on* handlers, javascript: URLs, etc.
 */

const SAFE_TAGS = new Set([
  "P", "BR", "STRONG", "B", "EM", "I", "U", "SPAN", "DIV",
  "UL", "OL", "LI", "A", "H1", "H2", "H3", "H4", "H5", "H6",
  "BLOCKQUOTE", "PRE", "HR",
]);

const SAFE_ATTRS = new Set(["href", "title", "target", "rel", "colspan", "rowspan"]);

const isSafeUrl = (url: string | null | undefined): boolean => {
  if (!url) return false;
  const v = url.trim().toLowerCase();
  if (v.startsWith("javascript:") || v.startsWith("data:") || v.startsWith("vbscript:")) return false;
  return v.startsWith("http://") || v.startsWith("https://") || v.startsWith("/") || v.startsWith("#") || v.startsWith("mailto:");
};

export function sanitizeHtml(input: string): string {
  if (!input) return "";
  // Se não parece HTML, devolve como texto puro (o React escapa sozinho no caller).
  if (!/<[a-zA-Z!/][^>]*>/.test(input)) return input;

  const doc = document.implementation.createHTMLDocument("");
  const root = doc.createElement("div");
  root.innerHTML = input;

  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null);
  const toRemove: Element[] = [];

  let node = walker.currentNode as Element;
  while (node) {
    const tag = node.tagName;
    if (!SAFE_TAGS.has(tag)) {
      // Tag não whitelisted: marca para remover, mas preserva o conteúdo de
      // formatação (ex.: <font> vira texto). Scripts/styles/iframes são
      // descartados inteiros já no walker (não iteramos conteúdo deles porque
      // criamos destructive removeChild ao coletar).
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "IFRAME" || tag === "OBJECT" || tag === "EMBED") {
        toRemove.push(node);
      } else {
        // unwrap: substitui o nó pelo seu conteúdo
        const parent = node.parentNode;
        if (parent) {
          while (node.firstChild) parent.insertBefore(node.firstChild, node);
          toRemove.push(node);
        }
      }
    } else {
      // Limpa atributos perigosos
      for (const attr of Array.from(node.attributes)) {
        const name = attr.name.toLowerCase();
        if (name.startsWith("on") || !SAFE_ATTRS.has(name.toUpperCase())) {
          node.removeAttribute(attr.name);
          continue;
        }
        if (name === "href" && !isSafeUrl(attr.value)) {
          node.removeAttribute(attr.name);
        }
      }
      // Força links externos a abrirem de forma segura
      if (tag === "A") {
        node.setAttribute("target", "_blank");
        node.setAttribute("rel", "noopener noreferrer");
      }
    }
    node = walker.nextNode() as Element;
  }

  for (const el of toRemove) el.parentNode?.removeChild(el);
  return root.innerHTML;
}

/**
 * Extrai uma versão curta de texto puro (sem tags) para uso em previews/truncate
 * de listas. Converte <br> e </p> em quebra de linha, depois stripa o resto.
 */
export function previewText(input: string, maxChars = 180): string {
  if (!input) return "";
  // Converte quebras HTML em espaço, descarta tags, normaliza espaços.
  const withBreaks = input
    .replace(/<\/(p|div|li|h[1-6])>/gi, " ")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  const flat = withBreaks.replace(/\s+/g, " ").trim();
  return flat.length > maxChars ? flat.slice(0, maxChars).trimEnd() + "…" : flat;
}