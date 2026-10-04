/** Thin client for the FastAPI backend.
 *
 * Paths are relative: Vite proxies /api and /images to the backend, so every
 * request is same-origin and the session cookie rides along automatically. */

export const API_BASE = "";

/** A short product loop. Present on hero products only; null for the rest. */
export type Motion = {
  preset: string;
  caption: string;
  webm: string;
  mp4: string;
  bytes: { webm: number; mp4: number };
};

export type Product = {
  product_id: string;
  motion?: Motion | null;
  name: string;
  garment_type: string;
  category: string;
  description: string;
  colors: string[];
  search_tags: string[];
  image_url: string;
  price: number;
  total_stock?: number;
  in_stock?: boolean;
};

export type ProductDetail = Product & {
  sizes: { size: string; quantity: number; in_stock: boolean }[];
};

export type Category = { name: string; count: number };

export type ChatTurn = { role: "user" | "assistant"; content: string };

/** The agent's reply. `products` is the structured half the page renders. */
export type ChatReply = {
  reply: string;
  /** Products the agent actually looked up — straight from the database. */
  products: Product[];
  /** What was searched for, used as the heading above the grid. */
  query: string;
  /** Total matches; can exceed products.length when the list was capped. */
  total_found: number;
  tools_used: string[];
  model: string;
};

/** Image paths come back relative so the backend host stays in one place. */
export const imageUrl = (product: Product) => `${API_BASE}${product.image_url}`;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function listProducts(params: { category?: string; search?: string } = {}) {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query}` : "";
  return getJson<{ count: number; products: Product[] }>(`/api/products${suffix}`);
}

export const getProduct = (id: string) =>
  getJson<ProductDetail>(`/api/products/${encodeURIComponent(id)}`);

export const listCategories = () => getJson<Category[]>("/api/categories");

// --- Recently viewed ----------------------------------------------------------

export type ViewedProduct = Product & { viewed_at: string; view_count: number };

/** Fire-and-forget: a failure here must never interrupt browsing. */
export function trackProductView(productId: string): void {
  fetch(`${API_BASE}/api/products/${encodeURIComponent(productId)}/view`, {
    method: "POST",
    credentials: "same-origin",
  }).catch(() => undefined);
}

export async function fetchRecentlyViewed(limit = 8): Promise<ViewedProduct[]> {
  const res = await fetch(`${API_BASE}/api/products/recently-viewed?limit=${limit}`, {
    credentials: "same-origin",
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.products ?? [];
}

export const clearRecentlyViewed = () =>
  fetch(`${API_BASE}/api/products/recently-viewed`, {
    method: "DELETE",
    credentials: "same-origin",
  });

/** Where the shopper is standing, so "do you have this in pink?" resolves. */
export type PageContext = { path: string; product_id?: string | null };

export type StoredMessage = {
  role: "user" | "assistant";
  content: string;
  products: Product[];
  created_at: string;
};

/**
 * Send one message.
 *
 * `history` is only used for guests — a logged-in shopper's thread is loaded from
 * the database server-side, so the browser cannot rewrite what was said.
 */
export async function sendChat(
  message: string,
  history: ChatTurn[] = [],
  page?: PageContext,
): Promise<ChatReply> {
  return postJson<ChatReply>("/api/chat", { message, history, page });
}

/** The logged-in shopper's saved conversation. Guests get an empty list. */
export async function fetchChatHistory(): Promise<StoredMessage[]> {
  const res = await fetch(`${API_BASE}/api/chat/history`, { credentials: "same-origin" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.messages ?? [];
}

export const clearChatHistory = () =>
  fetch(`${API_BASE}/api/chat/history`, { method: "DELETE", credentials: "same-origin" });

// --- Auth ---------------------------------------------------------------------

export type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
};

export type RegisterInput = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
};

/** Extra fields the login endpoint attaches to a failure. */
export type AuthErrorInfo = {
  /** Present after a wrong password: tries left before lockout. */
  attempts_remaining?: number;
  /** Present when locked out: seconds until the next attempt is allowed. */
  retry_after?: number;
};

/** Error carrying the server's human-readable reason, not just a status code. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public info: AuthErrorInfo = {},
  ) {
    super(message);
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const { message, info } = await readError(res);
    throw new ApiError(res.status, message, info);
  }
  return res.json() as Promise<T>;
}

/** FastAPI's `detail` arrives in three shapes: a string (plain HTTPException), an
 *  object (our structured auth errors), or a list (validation failures). Reduce
 *  all three to one readable sentence plus any structured extras. */
async function readError(res: Response): Promise<{ message: string; info: AuthErrorInfo }> {
  try {
    const { detail } = await res.json();
    if (typeof detail === "string") return { message: detail, info: {} };
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const { message, ...info } = detail as { message: string } & AuthErrorInfo;
      return { message, info };
    }
    if (Array.isArray(detail)) {
      const message = detail
        .map((d: { loc?: string[]; msg?: string }) => {
          const field = d.loc?.[d.loc.length - 1]?.replace("_", " ");
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join(" · ");
      return { message, info: {} };
    }
  } catch {
    /* fall through */
  }
  return { message: `${res.status} ${res.statusText}`, info: {} };
}

export const register = (input: RegisterInput) => postJson<User>("/api/auth/register", input);

export const login = (email: string, password: string) =>
  postJson<User>("/api/auth/login", { email, password });

export const logout = () => postJson<{ ok: boolean }>("/api/auth/logout", {});

export const forgotPassword = (email: string) =>
  postJson<{ message: string }>("/api/auth/forgot-password", { email });

export const resetPassword = (token: string, password: string, confirm_password: string) =>
  postJson<{ message: string }>("/api/auth/reset-password", { token, password, confirm_password });

export async function fetchMe(): Promise<User | null> {
  const res = await fetch(`${API_BASE}/api/auth/me`, { credentials: "same-origin" });
  return res.ok ? res.json() : null;
}
