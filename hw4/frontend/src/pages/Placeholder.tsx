import { Link } from "react-router-dom";
import "./Pages.css";

type Props = {
  eyebrow: string;
  title: string;
  body: string;
  /** Omitted for pages that are finished by design, such as the 404. */
  problem?: string;
};

/**
 * Honest stand-in for a route that is wired up but not yet built. Each one names
 * the homework problem that will replace it, so an unfinished page never reads
 * as a broken one.
 */
export default function Placeholder({ eyebrow, title, body, problem }: Props) {
  return (
    <article className="shell page">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="page__lede">{body}</p>

      {problem && (
        <p className="page__note">
          <strong>Not yet built.</strong> This page arrives with {problem}.
        </p>
      )}

      <div className="page__actions">
        <Link to="/" className="btn btn--ghost">
          Back to the Front Door
        </Link>
      </div>
    </article>
  );
}
