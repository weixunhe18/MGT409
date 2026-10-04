import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import ThemeSwitcher from "./ThemeSwitcher";
import "./NavBar.css";

/** Primary pages, in the order a shopper meets them. */
const PAGES = [
  { to: "/", label: "Home", end: true },
  { to: "/products", label: "Products", end: false },
  { to: "/about", label: "About Us", end: false },
];

export default function NavBar() {
  const { user, checking, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className="nav">
      <div className="nav__banner">Officially Licensed Yale Merchandise</div>

      <nav className="nav__bar shell" aria-label="Main">
        <NavLink to="/" className="nav__brand">
          <span className="nav__brand-mark">Y</span>
          <span className="nav__brand-text">
            <strong>Campus Customs</strong>
            <em>Yale Bulldog Blue</em>
          </span>
        </NavLink>

        <ul className="nav__links">
          {PAGES.map((page) => (
            <li key={page.to}>
              <NavLink
                to={page.to}
                end={page.end}
                className={({ isActive }) =>
                  isActive ? "nav__link nav__link--active" : "nav__link"
                }
              >
                {page.label}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* Hidden while the first /me check is in flight, so a logged-in
            shopper never sees "Log In" flash before their name appears. */}
        <ThemeSwitcher />

        <div className="nav__account" aria-busy={checking}>
          {checking ? null : user ? (
            <>
              <span className="nav__greeting">
                Welcome, <strong>{user.first_name}</strong>
              </span>
              <button type="button" className="nav__login nav__logout" onClick={handleLogout}>
                Log Out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="nav__login">
                Log In
              </NavLink>
              <NavLink to="/create-account" className="nav__cta">
                Create Account
              </NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
