import { Link } from "react-router-dom";

import type { Product } from "../api";
import MotionMedia from "./MotionMedia";

/**
 * One product card in the grid.
 *
 * Deliberately the only card component on the site. The browse grid and the
 * chat-driven results render *this*, so a card the chat just put on the page is
 * the same element as one that was always there — same link, same detail page,
 * no second code path that could drift.
 */
export default function ProductGridCard({ product }: { product: Product }) {
  return (
    <Link to={`/products/${product.product_id}`} className="card">
      <div className="card__frame">
        <MotionMedia product={product} hoverToPlay />
        {product.in_stock === false && <span className="card__sold">Sold out</span>}
      </div>
      <div className="card__body">
        <span className="card__cat">{product.category}</span>
        <h3>{product.name}</h3>
        <p className="card__colors">{product.colors.join(", ")}</p>
        <p className="card__price">${product.price.toFixed(2)}</p>
      </div>
    </Link>
  );
}
