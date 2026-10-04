import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { Product } from "./api";

export type ChatResults = {
  /** What the shopper asked for, used as the grid heading. */
  query: string;
  products: Product[];
  /** Total matches found, which can exceed `products.length` when capped. */
  totalFound: number;
};

type ChatResultsState = {
  results: ChatResults | null;
  show: (results: ChatResults) => void;
  clear: () => void;
};

const ChatResultsContext = createContext<ChatResultsState | null>(null);

/**
 * Holds the product matches the agent returned, so the chat panel can hand them
 * to the Products page.
 *
 * Kept in context rather than in the URL because these results are the output of
 * a conversation, not a bookmarkable query — reloading the page should return the
 * shopper to the full catalogue, not replay a chat turn.
 */
export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ChatResults | null>(null);

  const show = useCallback((next: ChatResults) => setResults(next), []);
  const clear = useCallback(() => setResults(null), []);

  const value = useMemo(() => ({ results, show, clear }), [results, show, clear]);
  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>;
}

export function useChatResults(): ChatResultsState {
  const ctx = useContext(ChatResultsContext);
  if (!ctx) throw new Error("useChatResults must be used inside <ChatResultsProvider>");
  return ctx;
}
