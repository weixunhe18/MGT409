import { Link } from "react-router-dom";
import "./Pages.css";

export default function About() {
  return (
    <article className="shell page">
      <p className="eyebrow">About Us</p>
      <h1>In Which the Proprietor Explains Himself</h1>

      <p className="page__lede">
        A shop, like a republic, is held together by nothing grander than the
        habit of telling the truth about small matters. Ours is cloth.
      </p>

      <h2>Of the Merchandise</h2>
      <p>
        We deal in officially licensed Yale apparel and nothing besides: crewnecks,
        hoodies, T-shirts, quarter-zips, and jackets fit for a February on Elm
        Street. One hundred and two articles in all, each in six sizes from the
        smallest to the sixth, which is to say we have tried to anticipate the
        whole range of the human frame without pretending to have succeeded.
      </p>
      <p>
        You will find the residential colleges represented &mdash; Berkeley,
        Branford, Davenport, and one bearing my own name, which I confess I did
        not ask for and shall not pretend to resent. A man who spent his youth
        setting another printer&rsquo;s type does not object to seeing his name
        well set at last.
      </p>

      <h2>Of Honesty in Trade</h2>
      <p>
        I have long held that the first duty of a tradesman is not enthusiasm but
        accuracy. Our storeroom keeps six hundred and twelve counts of stock, and
        of those a fair number stand at nothing at all. We do not hide this. If
        you want a Large and the Large is spent, you will be told so at once,
        rather than discovering it by a letter three weeks hence.
      </p>
      <p>
        The same rule governs the price. Our goods run from thirty-two dollars to
        ninety-eight, and the figure you are shown is the figure we hold. I have
        read a great deal of fine print in my life, most of it composed by men
        who hoped I would not.
      </p>

      <h2>Of the Mechanical Clerk</h2>
      <p>
        We employ an assistant that is not, strictly speaking, alive. It reads the
        storeroom ledger directly and answers from it. Ask it what we keep in navy,
        what a fleece costs, or whether anything bears the Bulldog, and it will
        tell you. Ask it for gymnasium shorts &mdash; which we do not stock &mdash;
        and it will say so rather than invent a pair to please you.
      </p>
      <p>
        I am told this restraint is difficult to engineer. Having known a number of
        salesmen, I believe it.
      </p>

      <h2>Of Your Account</h2>
      <p>
        Establish an account and the clerk will remember you: your name, and what
        you came looking for last. This is a convenience, not a surveillance. I
        have kept correspondence with half of Europe and never found memory to be
        the offensive part of a friendship.
      </p>

      <div className="page__actions">
        <Link to="/products" className="btn btn--primary">
          Browse the Goods
        </Link>
        <Link to="/create-account" className="btn btn--ghost">
          Open an Account
        </Link>
      </div>

      <p className="page__sig">
        Yours in commerce and in reasonable weather,
        <br />
        <strong>B. Franklin</strong>
        <br />
        <em>Proprietor in Spirit, Campus Customs</em>
      </p>
    </article>
  );
}
