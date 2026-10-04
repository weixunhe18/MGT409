import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { clearChatHistory, fetchChatHistory, imageUrl, sendChat } from "../api";
import type { ChatTurn, PageContext, Product } from "../api";
import { useAuth } from "../auth";
import { useChatResults } from "../chatResults";
import HandsomeDan from "./HandsomeDan";
import Markdown from "./Markdown";
import "./ChatWidget.css";

/** Turns the agent sends back as context. Caps the thread so a long session does
 *  not grow the request without limit; the server caps it too. */
const HISTORY_LIMIT = 12;

type Message = {
  role: "user" | "assistant";
  content: string;
  products?: Product[];
};

const GREETING: Message = {
  role: "assistant",
  content:
    "Woof. I'm Handsome Dan. Ask me about anything in the storeroom — sizes, colors, what a thing costs.",
};

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { show } = useChatResults();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, checking } = useAuth();
  const [restoring, setRestoring] = useState(false);

  // Load the saved thread when a member arrives or logs in; wipe it on logout so
  // one shopper's conversation never lingers on screen for the next.
  useEffect(() => {
    if (checking) return;

    if (!user) {
      setMessages([GREETING]);
      return;
    }

    let cancelled = false;
    setRestoring(true);
    fetchChatHistory()
      .then((stored) => {
        if (cancelled) return;
        setMessages(
          stored.length
            ? stored.map((m) => ({
                role: m.role,
                content: m.content,
                products: m.products ?? [],
              }))
            : [GREETING],
        );
      })
      .finally(() => !cancelled && setRestoring(false));

    return () => {
      cancelled = true;
    };
  }, [user, checking]);

  /** Current page, so the agent can resolve "this" and "it". */
  function pageContext(): PageContext {
    const match = /^\/products\/(.+)$/.exec(location.pathname);
    return { path: location.pathname, product_id: match ? match[1] : null };
  }

  async function forget() {
    await clearChatHistory();
    setMessages([GREETING]);
  }

  // Keep the newest message in view, and focus the field when the panel opens.
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || pending) return;

    // Built before the new turn is appended, so the agent sees the thread as it
    // stood when the shopper typed. The greeting is ours, not part of the thread.
    const history: ChatTurn[] = messages
      .filter((m) => m !== GREETING)
      .slice(-HISTORY_LIMIT)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setDraft("");
    setPending(true);

    try {
      const reply = await sendChat(text, history, pageContext());
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, products: reply.products },
      ]);

      // The structured half of the reply drives the page, not just this panel.
      if (reply.products.length > 0) {
        show({
          query: reply.query,
          products: reply.products,
          totalFound: reply.total_found || reply.products.length,
        });
        // Put the shopper where the grid is. Showing matches on a page with no
        // grid would be the feature quietly doing nothing.
        //
        // Exact match, not startsWith: "/products/some-hoodie" is a detail page,
        // which has no grid to repaint. Asking a category question from a product
        // page used to set the results and leave the shopper staring at the item
        // they were already looking at.
        if (location.pathname !== "/products") navigate("/products");
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `I can't reach the shop just now — ${(err as Error).message}`,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="dan-launcher"
        onClick={() => setOpen(true)}
        aria-label="Open chat with Handsome Dan"
      >
        <HandsomeDan size={46} />
        <span className="dan-launcher__pip" aria-hidden="true" />
      </button>
    );
  }

  return (
    <section className="dan-panel" aria-label="Chat with Handsome Dan">
      <header className="dan-panel__head">
        <HandsomeDan size={34} />
        <div className="dan-panel__title">
          <strong>Handsome Dan</strong>
          <span>{user ? `Remembering for ${user.first_name}` : "Shop clerk · guest chat"}</span>
        </div>
        {user && (
          <button
            type="button"
            className="dan-panel__forget"
            onClick={forget}
            title="Delete this conversation from your account"
          >
            Forget
          </button>
        )}
        <button
          type="button"
          className="dan-panel__close"
          onClick={() => setOpen(false)}
          aria-label="Close chat"
        >
          &times;
        </button>
      </header>

      <div className="dan-panel__log" ref={logRef}>
        {restoring && <p className="dan-panel__restoring">Fetching what we talked about&hellip;</p>}
        {messages.map((message, index) => (
          <div key={index} className="turn">
            <div className={`bubble bubble--${message.role}`}>
              {message.role === "assistant" ? (
                <Markdown text={message.content} />
              ) : (
                message.content
              )}
            </div>
            {message.products && message.products.length > 0 && (
              <ul className="dan-products">
                {message.products.map((product) => (
                  <li key={product.product_id}>
                    <Link
                      to={`/products/${product.product_id}`}
                      className="dan-product"
                      onClick={() => setOpen(false)}
                    >
                      <img src={imageUrl(product)} alt="" loading="lazy" />
                      <span className="dan-product__text">
                        <strong>{product.name}</strong>
                        <span>${product.price.toFixed(2)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {pending && (
          <div className="bubble bubble--assistant bubble--typing">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      <form className="dan-panel__form" onSubmit={submit}>
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about a hoodie, a size, a price…"
          aria-label="Message Handsome Dan"
        />
        <button type="submit" disabled={pending || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
