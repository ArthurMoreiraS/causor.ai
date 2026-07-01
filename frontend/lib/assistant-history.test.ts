import { describe, expect, it } from "vitest";
import type { ChatTurn } from "./api";
import {
  ASSISTANT_HISTORY_LIMIT,
  createAssistantConversation,
  deriveConversationTitle,
  loadAssistantConversations,
  saveAssistantConversations,
  upsertAssistantConversation
} from "./assistant-history";

function memoryStorage(initial?: string) {
  const values = new Map<string, string>();
  if (initial != null) values.set("causor.assistant.conversations.v1", initial);
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    value: (key: string) => values.get(key)
  };
}

describe("assistant conversation history", () => {
  it("derives a compact title from the first user message", () => {
    const turns: ChatTurn[] = [
      { role: "assistant", content: "Como posso ajudar?" },
      {
        role: "user",
        content: "   Quais prazos exigem atenção hoje e quais minutas precisam de aprovação?   "
      }
    ];

    expect(deriveConversationTitle(turns)).toBe("Quais prazos exigem atenção hoje e quais...");
    expect(deriveConversationTitle([])).toBe("Nova conversa");
  });

  it("upserts conversations by recency and caps the local history", () => {
    const existing = Array.from({ length: ASSISTANT_HISTORY_LIMIT }, (_, index) =>
      createAssistantConversation({
        id: `old-${index}`,
        now: `2026-07-01T10:${String(index).padStart(2, "0")}:00.000Z`,
        turns: [{ role: "user", content: `Conversa ${index}` }]
      })
    );
    const next = createAssistantConversation({
      id: "new",
      now: "2026-07-01T12:00:00.000Z",
      turns: [{ role: "user", content: "Nova prioridade operacional" }]
    });

    const result = upsertAssistantConversation(existing, next);

    expect(result).toHaveLength(ASSISTANT_HISTORY_LIMIT);
    expect(result[0].id).toBe("new");
    expect(result.some((item) => item.id === "old-0")).toBe(false);
    expect(result[0].title).toBe("Nova prioridade operacional");
  });

  it("loads only valid stored conversations and ignores malformed storage", () => {
    const valid = createAssistantConversation({
      id: "valid",
      now: "2026-07-01T12:00:00.000Z",
      turns: [{ role: "user", content: "Resumo da fila" }]
    });
    const storage = memoryStorage(JSON.stringify([valid, { id: "broken", turns: "not-array" }]));

    expect(loadAssistantConversations(storage)).toEqual([valid]);
    expect(loadAssistantConversations(memoryStorage("{bad json"))).toEqual([]);
  });

  it("saves normalized conversations to storage", () => {
    const storage = memoryStorage();
    const conversation = createAssistantConversation({
      id: "case",
      now: "2026-07-01T12:00:00.000Z",
      turns: [{ role: "user", content: "Analise os prazos vencidos" }]
    });

    saveAssistantConversations(storage, [conversation]);

    expect(JSON.parse(storage.value("causor.assistant.conversations.v1") ?? "[]")).toEqual([
      conversation
    ]);
  });
});
