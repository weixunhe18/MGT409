import { Link } from "react-router-dom";
import "./Pages.css";

/**
 * Categories mirror the five normalized groups the backend derives from the
 * catalogue's messy `garment_type` column, so the copy never promises a filter
 * the database cannot honor.
 */
const DEPARTMENTS = [
  { name: "Crewnecks", count: 29, note: "Plain-spoken warmth, collar to cuff." },
  { name: "Hoodies", count: 27, note: "A roof for the head, carried about." },
  { name: "T-Shirts", count: 27, note: "Light cloth for the heavier months." },
  { name: "Quarter-Zips", count: 11, note: "Adjustable, as a sensible man is." },
  { name: "Jackets", count: 8, note: "For a New Haven wind that argues back." },
];

const MAXIMS = [
  {
    head: "Officially Licensed",
    body: "Every thread here is sanctioned by the University. We sell no counterfeit, and we flatter no imitation.",
  },
  {
    head: "An Honest Inventory",
    body: "If a size is gone, we say it is gone. A merchant who promises what he lacks has sold you nothing but a delay.",
  },
  {
    head: "The Price Plainly Stated",
    body: "From $32 to $98, and no figure hidden in the small print. A bargain concealed is a bargain doubted.",
  },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="shell hero__inner">
          <p className="eyebrow">New Haven, Connecticut · Est. for the Bulldogs</p>
          <h1>
            Good Cloth, Honestly Sold,
            <br />
            to the Sons and Daughters of Yale
          </h1>
          <p className="hero__lede">
            I have printed almanacks, flown kites in weather no sensible man
            would walk in, and signed a document or two of consequence. Yet I
            find a well-made sweatshirt gives a comfort that the Continental
            Congress never did. Welcome to Campus Customs.
          </p>
          <div className="hero__actions">
            <Link to="/products" className="btn btn--primary">
              Browse the Goods
            </Link>
            <Link to="/about" className="btn btn--ghost">
              Our Particulars
            </Link>
          </div>
          <p className="hero__sig">— B. Franklin, Proprietor in Spirit</p>
        </div>
      </section>

      <section className="shell band">
        <div className="maxims">
          {MAXIMS.map((maxim) => (
            <article key={maxim.head} className="maxim">
              <h3>{maxim.head}</h3>
              <p>{maxim.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="shell band">
        <header className="band__head">
          <h2>The Departments</h2>
          <p>
            One hundred and two articles of apparel, sorted into five honest
            categories. I am told the shopkeepers before me used two-and-twenty
            names for the same five things, which is two-and-twenty ways to lose
            a customer.
          </p>
        </header>

        <ul className="departments">
          {DEPARTMENTS.map((dept) => (
            <li key={dept.name}>
              <Link to="/products" className="department">
                <span className="department__count">{dept.count}</span>
                <span className="department__name">{dept.name}</span>
                <span className="department__note">{dept.note}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="shell band">
        <div className="callout">
          <h2>A Word on the Shop&rsquo;s Clerk</h2>
          <p>
            You will find upon these pages an assistant of uncommon construction
            &mdash; it does not sleep, does not tire, and has read every label in
            the storeroom. Ask it for a fleece, or for something bearing the
            Bulldog, and it will fetch what we truly have. Ask it for breeches
            and it will tell you plainly that we keep none. I have met men who
            could not manage as much.
          </p>
          <Link to="/products" className="btn btn--primary">
            Put It to the Question
          </Link>
        </div>
      </section>
    </>
  );
}
