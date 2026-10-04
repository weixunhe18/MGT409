import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getProduct, imageUrl, trackProductView } from "../api";
import type { ProductDetail as Detail } from "../api";
import { useAuth } from "../auth";
import MotionMedia from "../components/MotionMedia";
import "./Pages.css";
import "./Products.css";

export default function ProductDetail() {
  const { productId = "" } = useParams();
  const [product, setProduct] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user, checking } = useAuth();

  useEffect(() => {
    setProduct(null);
    setError(null);
    getProduct(productId)
      .then(setProduct)
      .catch((err: Error) => setError(err.message));
  }, [productId]);

  // Recorded on open rather than on click, so arriving by link, by chat card, or
  // by typing the URL all count the same. Members only; the server ignores guests.
  useEffect(() => {
    if (!checking && user && productId) trackProductView(productId);
  }, [productId, user, checking]);

  if (error) {
    return (
      <div className="shell page">
        <h1>No Such Article</h1>
        <p className="page__note">
          <strong>{error}.</strong> We keep no product by the name
          &ldquo;{productId}&rdquo;.
        </p>
        <div className="page__actions">
          <Link to="/products" className="btn btn--ghost">
            Back to the Storeroom
          </Link>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="shell page">
        <p className="muted">Fetching the article&hellip;</p>
      </div>
    );
  }

  const sizesInStock = product.sizes.filter((s) => s.in_stock).length;

  return (
    <div className="shell page page--wide">
      <p className="eyebrow">
        <Link to="/products">Products</Link> &nbsp;/&nbsp; {product.category}
      </p>

      <div className="detail">
        <div className="detail__image">
          {/* No width/height attributes: the catalogue images are not uniform
              (900x900 down to 450x450, and a handful are 720x900 or 600x900),
              so a declared square ratio stretched the rectangular ones. */}
          {product.motion ? (
            <div className="motion--detail">
              <MotionMedia product={product} />
            </div>
          ) : (
            <img src={imageUrl(product)} alt={product.name} />
          )}
        </div>

        <div>
          <h1>{product.name}</h1>
          <p className="detail__price">${product.price.toFixed(2)}</p>
          <p className="detail__desc">{product.description}</p>

          <div className="detail__row">
            <span className="detail__label">Colors</span>
            <ul className="tags">
              {product.colors.map((color) => (
                <li key={color} className="tag">
                  {color}
                </li>
              ))}
            </ul>
          </div>

          <div className="detail__row">
            <span className="detail__label">
              Sizes &mdash;{" "}
              {sizesInStock === 0
                ? "none left in any size"
                : `${sizesInStock} of ${product.sizes.length} available`}
            </span>
            <ul className="sizes">
              {product.sizes.map((size) => (
                <li
                  key={size.size}
                  className={size.in_stock ? "size" : "size size--out"}
                  title={
                    size.in_stock
                      ? `${size.quantity} in stock`
                      : "Out of stock"
                  }
                >
                  {size.size}
                  <small>{size.in_stock ? `${size.quantity} left` : "none"}</small>
                </li>
              ))}
            </ul>
          </div>

          <div className="detail__row">
            <span className="detail__label">Tags</span>
            <ul className="tags">
              {product.search_tags.map((tag) => (
                <li key={tag} className="tag">
                  {tag}
                </li>
              ))}
            </ul>
          </div>

          <p className="detail__meta">
            Catalogue type: {product.garment_type} &middot; shelved under{" "}
            {product.category} &middot; {product.total_stock} units in all sizes
          </p>

          <div className="page__actions">
            <Link to="/products" className="btn btn--ghost">
              Back to the Storeroom
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
