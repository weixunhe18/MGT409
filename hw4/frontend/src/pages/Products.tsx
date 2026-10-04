import { useEffect, useState } from "react";

import { clearRecentlyViewed, fetchRecentlyViewed, listCategories, listProducts } from "../api";
import type { Category, Product, ViewedProduct } from "../api";
import { useAuth } from "../auth";
import { useChatResults } from "../chatResults";
import HandsomeDan from "../components/HandsomeDan";
import ProductGridCard from "../components/ProductGridCard";
import "./Pages.css";
import "./Products.css";

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Matches the agent put on the page. While these are showing they replace the
  // browse grid; clearing them, or picking a category chip, returns to the catalogue.
  const { results, clear } = useChatResults();

  const { user, checking } = useAuth();
  const [recent, setRecent] = useState<ViewedProduct[]>([]);

  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  // Refetched whenever the shopper changes, so logging out empties it and logging
  // back in restores it.
  useEffect(() => {
    if (checking) return;
    if (!user) {
      setRecent([]);
      return;
    }
    fetchRecentlyViewed().then(setRecent).catch(() => setRecent([]));
  }, [user, checking]);

  async function forgetRecent() {
    await clearRecentlyViewed();
    setRecent([]);
  }

  useEffect(() => {
    setLoading(true);
    listProducts(active ? { category: active } : {})
      .then((data) => {
        setProducts(data.products);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [active]);

  function pickCategory(category: string | null) {
    clear(); // a deliberate browse replaces whatever the chat put up
    setActive(category);
  }

  return (
    <div className="shell page page--wide">
      <p className="eyebrow">Products</p>
      <h1>The Storeroom</h1>
      <p className="page__lede">
        Everything we keep, laid out plainly. The count beside each department is
        the true number on the shelf, not a hopeful estimate.
      </p>

      {/* Members only. Sits above the browse controls so a returning shopper picks
          up where they left off before deciding what to look at next. */}
      {user && recent.length > 0 && (
        <section className="recent">
          <header className="recent__head">
            <h2>Recent Products Viewed</h2>
            <button type="button" className="recent__clear" onClick={forgetRecent}>
              Clear
            </button>
          </header>
          <ul className="grid grid--compact">
            {recent.map((product) => (
              <li key={product.product_id}>
                <ProductGridCard product={product} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="filters">
        <button
          type="button"
          className={active === null && !results ? "chip chip--active" : "chip"}
          onClick={() => pickCategory(null)}
        >
          All
        </button>
        {categories.map((category) => (
          <button
            key={category.name}
            type="button"
            className={active === category.name && !results ? "chip chip--active" : "chip"}
            onClick={() => pickCategory(category.name)}
          >
            {category.name} <span className="chip__count">{category.count}</span>
          </button>
        ))}
      </div>

      {results ? (
        <section className="chat-results">
          <header className="chat-results__head">
            <HandsomeDan size={34} />
            <div>
              <h2>
                Handsome Dan found {results.totalFound}{" "}
                {results.totalFound === 1 ? "match" : "matches"}
                {results.query ? (
                  <>
                    {" "}
                    for <em>{results.query}</em>
                  </>
                ) : null}
              </h2>
              <p>
                {results.totalFound > results.products.length
                  ? `Showing the first ${results.products.length}. `
                  : ""}
                Click any card for the full details.
              </p>
            </div>
            <button type="button" className="chip" onClick={() => clear()}>
              Show all products
            </button>
          </header>

          <ul className="grid">
            {results.products.map((product) => (
              <li key={product.product_id}>
                <ProductGridCard product={product} />
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <>
          {error && (
            <p className="page__note">
              <strong>The storeroom will not answer.</strong> {error} &mdash; is the
              backend running on port 8000?
            </p>
          )}

          {loading && !error && <p className="muted">Fetching the goods&hellip;</p>}

          {!loading && !error && (
            <>
              <p className="muted">
                Showing {products.length}{" "}
                {products.length === 1 ? "article" : "articles"}
                {active ? ` in ${active}` : ""}.
              </p>

              <ul className="grid">
                {products.map((product) => (
                  <li key={product.product_id}>
                    <ProductGridCard product={product} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
