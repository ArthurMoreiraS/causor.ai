import type { ChatTurn, ProposedAction } from "./api";

export const ASSISTANT_HISTORY_STORAGE_KEY = "causor.assistant.conversations.v1";
export const ASSISTANT_HISTORY_LIMIT = 12;

export type AssistantConversation = {
  id: string;
  title: string;
  turns: ChatTurn[];
  pending: ProposedAction[];
  createdAt: string;
  updatedAt: string;
};

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

type ConversationInput = Partial<Pick<AssistantConversation, "id" | "turns" | "pending">> & {
  now?: string;
};

function newConversationId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `assistant-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function deriveConversationTitle(turns: ChatTurn[]) {
  const firstUserMessage = turns.find((turn) => turn.role === "user")?.content.trim();
  if (!firstUserMessage) return "Nova conversa";
  const normalized = firstUserMessage.replace(/\s+/g, " ");
  if (normalized.length <= 44) return normalized;
  return `${normalized.slice(0, 41).trim()}...`;
}

export function createAssistantConversation(input: ConversationInput = {}): AssistantConversation {
  const now = input.now ?? new Date().toISOString();
  const turns = input.turns ?? [];
  return {
    id: input.id ?? newConversationId(),
    title: deriveConversationTitle(turns),
    turns,
    pending: input.pending ?? [],
    createdAt: now,
    updatedAt: now
  };
}

export function touchAssistantConversation(
  conversation: AssistantConversation,
  patch: Partial<Pick<AssistantConversation, "turns" | "pending">> = {},
  now = new Date().toISOString()
): AssistantConversation {
  const turns = patch.turns ?? conversation.turns;
  return {
    ...conversation,
    ...patch,
    turns,
    title: deriveConversationTitle(turns),
    updatedAt: now
  };
}

function isChatTurn(value: unknown): value is ChatTurn {
  if (typeof value !== "object" || value == null) return false;
  const turn = value as Partial<ChatTurn>;
  return (turn.role === "user" || turn.role === "assistant") && typeof turn.content === "string";
}

function isConversation(value: unknown): value is AssistantConversation {
  if (typeof value !== "object" || value == null) return false;
  const candidate = value as Partial<AssistantConversation>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.title === "string" &&
    Array.isArray(candidate.turns) &&
    candidate.turns.every(isChatTurn) &&
    Array.isArray(candidate.pending) &&
    typeof candidate.createdAt === "string" &&
    typeof candidate.updatedAt === "string"
  );
}

export function upsertAssistantConversation(
  conversations: AssistantConversation[],
  conversation: AssistantConversation
): AssistantConversation[] {
  const withoutCurrent = conversations.filter((item) => item.id !== conversation.id);
  return [conversation, ...withoutCurrent]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, ASSISTANT_HISTORY_LIMIT);
}

export function loadAssistantConversations(storage: StorageLike): AssistantConversation[] {
  const raw = storage.getItem(ASSISTANT_HISTORY_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isConversation).slice(0, ASSISTANT_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function saveAssistantConversations(
  storage: StorageLike,
  conversations: AssistantConversation[]
) {
  const normalized = conversations.filter(isConversation).slice(0, ASSISTANT_HISTORY_LIMIT);
  if (normalized.length === 0) {
    storage.removeItem(ASSISTANT_HISTORY_STORAGE_KEY);
    return;
  }
  storage.setItem(ASSISTANT_HISTORY_STORAGE_KEY, JSON.stringify(normalized));
}
