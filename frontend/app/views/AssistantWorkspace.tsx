"use client";

import {
  CalendarClock,
  Clock3,
  ListChecks,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { enviarMensagemChat } from "@/lib/api";
import type { ChatTurn, ProposedAction } from "@/lib/api";
import {
  type AssistantConversation,
  createAssistantConversation,
  loadAssistantConversations,
  saveAssistantConversations,
  touchAssistantConversation,
  upsertAssistantConversation
} from "@/lib/assistant-history";

export default function AssistantWorkspace({
  offline,
  onConfirmAction
}: {
  offline: boolean;
  onConfirmAction: (action: ProposedAction) => Promise<void>;
}) {
  const [conversation, setConversation] = useState<AssistantConversation>(() => createAssistantConversation());
  const [history, setHistory] = useState<AssistantConversation[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const turns = conversation.turns;
  const pending = conversation.pending;
  const messageCount = turns.length;
  const activePreview = useMemo(() => getConversationPreview(conversation), [conversation]);
  const visibleHistory = history.slice(0, 8);

  useEffect(() => {
    const loaded = loadAssistantConversations(window.localStorage);
    if (loaded.length === 0) return;
    setHistory(loaded);
    setConversation(loaded[0]);
  }, []);

  function commitConversation(next: AssistantConversation) {
    setConversation(next);
    if (next.turns.length === 0 && next.pending.length === 0) return;
    setHistory((current) => {
      const updated = upsertAssistantConversation(current, next);
      saveAssistantConversations(window.localStorage, updated);
      return updated;
    });
  }

  function startNewConversation() {
    setConversation(createAssistantConversation());
    setError(null);
  }

  function selectConversation(next: AssistantConversation) {
    if (busy) return;
    setConversation(next);
    setError(null);
  }

  function deleteConversation(id: string) {
    const updated = history.filter((item) => item.id !== id);
    setHistory(updated);
    saveAssistantConversations(window.localStorage, updated);
    if (conversation.id === id) {
      setConversation(updated[0] ?? createAssistantConversation());
      setError(null);
    }
  }

  function clearHistory() {
    setHistory([]);
    saveAssistantConversations(window.localStorage, []);
    setConversation(createAssistantConversation());
    setError(null);
  }

  async function send(textFromSuggestion?: string) {
    const text = (textFromSuggestion ?? input).trim();
    if (!text || busy || offline) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    const optimistic = touchAssistantConversation(conversation, { turns: next, pending: [] });
    commitConversation(optimistic);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const resp = await enviarMensagemChat(next);
      commitConversation(
        touchAssistantConversation(optimistic, {
          turns: [
            ...next,
            {
              role: "assistant",
              content: resp.reply || "Recebi a solicitação e preparei os próximos passos."
            }
          ],
          pending: resp.proposed_actions
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no assistente");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(action: ProposedAction) {
    setBusy(true);
    setError(null);
    try {
      await onConfirmAction(action);
      commitConversation(
        touchAssistantConversation(conversation, {
          pending: pending.filter((item) => item !== action),
          turns: [
            ...turns,
            { role: "assistant", content: `Ação executada: ${action.label}.` }
          ]
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ação não concluída");
    } finally {
      setBusy(false);
    }
  }

  const suggestions = [
    {
      icon: CalendarClock,
      title: "Priorizar prazos",
      prompt: "Quais prazos exigem atenção hoje?"
    },
    {
      icon: MessageSquare,
      title: "Intimações sem minuta",
      prompt: "Mostre as intimações sem minuta."
    },
    {
      icon: ShieldCheck,
      title: "Aprovação OAB",
      prompt: "Quais minutas aguardam aprovação OAB?"
    },
    {
      icon: ListChecks,
      title: "Plano de trabalho",
      prompt: "Monte meu plano de trabalho para hoje."
    },
    {
      icon: Search,
      title: "Processos parados",
      prompt: "Quais processos estão sem próxima ação?"
    }
  ];

  return (
    <section className="assistantWorkspace">
      <aside className="assistantHistoryPanel" aria-label="Histórico do assistente">
        <header className="assistantHistoryHeader">
          <div>
            <span>Histórico</span>
            <strong>{history.length} conversa{history.length === 1 ? "" : "s"}</strong>
          </div>
          <button
            type="button"
            className="iconButton"
            title="Nova conversa"
            aria-label="Nova conversa"
            disabled={busy}
            onClick={startNewConversation}
          >
            <Plus size={15} />
          </button>
        </header>

        <div className="assistantThreadList">
          {history.length === 0 ? (
            <div className="assistantThreadEmpty">
              <MessageSquare size={16} />
              <strong>Sem conversas ainda</strong>
              <span>Quando você enviar uma pergunta, o histórico local fica salvo aqui.</span>
            </div>
          ) : (
            visibleHistory.map((item) => (
              <article
                className={item.id === conversation.id ? "assistantThread active" : "assistantThread"}
                key={item.id}
              >
                <button
                  type="button"
                  className="assistantThreadMain"
                  disabled={busy}
                  onClick={() => selectConversation(item)}
                >
                  <strong>{item.title}</strong>
                  <span>{getConversationPreview(item)}</span>
                  <small>
                    <Clock3 size={11} />
                    {formatConversationDate(item.updatedAt)}
                  </small>
                </button>
                <button
                  type="button"
                  className="assistantThreadDelete"
                  title="Excluir conversa"
                  aria-label={`Excluir conversa ${item.title}`}
                  disabled={busy}
                  onClick={() => deleteConversation(item.id)}
                >
                  <Trash2 size={13} />
                </button>
              </article>
            ))
          )}
          {history.length > visibleHistory.length ? (
            <span className="assistantThreadMore">
              +{history.length - visibleHistory.length} conversa{history.length - visibleHistory.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>

        {history.length > 0 ? (
          <button className="assistantClearHistory" type="button" disabled={busy} onClick={clearHistory}>
            Limpar histórico local
          </button>
        ) : null}
      </aside>

      <div className="assistantMain">
        <header className="assistantSessionHeader">
          <div>
            <span className="sectionKicker">Assistente de IA</span>
            <h2>{conversation.title}</h2>
            {turns.length > 0 ? <p>{activePreview}</p> : null}
          </div>
          <div className="assistantSessionStats" aria-label="Resumo da conversa">
            <span>{messageCount} mensagens</span>
            <span>{pending.length} ações pendentes</span>
          </div>
        </header>

        <div className={turns.length === 0 ? "chatSurface empty" : "chatSurface active"}>
          {turns.length === 0 ? (
            <>
              <div className="assistantIntro">
                <span className="assistantIntroBadge">
                  <Sparkles size={15} />
                  Pronto para operar
                </span>
                <h3>Escolha uma ação ou pergunte livremente.</h3>
              </div>
              <div className="promptSuggestions" aria-label="Perguntas sugeridas">
                {suggestions.map((suggestion) => {
                  const Icon = suggestion.icon;
                  return (
                    <button
                      key={suggestion.prompt}
                      onClick={() => void send(suggestion.prompt)}
                      disabled={offline || busy}
                    >
                      <span className="promptIcon">
                        <Icon size={16} />
                      </span>
                      <span>
                        <strong>{suggestion.title}</strong>
                      </span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="chatTimeline">
              {turns.map((turn, index) => (
                <article className={`chatBubble ${turn.role}`} key={`${turn.role}-${index}`}>
                  <span>{turn.content}</span>
                </article>
              ))}
            </div>
          )}

          {pending.length ? (
            <div className="assistantActionShelf">
              {pending.map((action, index) => (
                <article className="assistantActionCard" key={`${action.tipo}-${index}`}>
                  <div>
                    <ShieldCheck size={15} />
                    <strong>{action.label}</strong>
                    <span>{action.endpoint}</span>
                  </div>
                  <div className="proposedActions">
                    <button
                      className="toolbarButton primary"
                      disabled={busy || offline}
                      onClick={() => void confirm(action)}
                    >
                      Confirmar
                    </button>
                    <button
                      className="toolbarButton"
                      disabled={busy}
                      onClick={() =>
                        commitConversation(
                          touchAssistantConversation(conversation, {
                            pending: pending.filter((item) => item !== action)
                          })
                        )
                      }
                    >
                      Descartar
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}

          {error ? <div className="assistantError wide">{error}</div> : null}
        </div>

        <form
          className="assistantComposer"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <textarea
            placeholder={offline ? "Backend offline" : "Pergunte ao Causor"}
            value={input}
            disabled={offline || busy}
            rows={1}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
          />
          <button className="iconButton" disabled={offline || busy || !input.trim()} type="submit">
            {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
          </button>
        </form>
      </div>
    </section>
  );
}

function getConversationPreview(conversation: AssistantConversation) {
  const lastTurn = conversation.turns.at(-1);
  if (lastTurn) return lastTurn.content;
  if (conversation.pending.length > 0) return `${conversation.pending.length} ação pendente`;
  return "Pronta para uma nova análise operacional.";
}

function formatConversationDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Agora";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
