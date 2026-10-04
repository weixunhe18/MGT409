import { Outlet } from "react-router-dom";
import ChatWidget from "./components/ChatWidget";
import NavBar from "./components/NavBar";
import "./pages/Pages.css";

export default function App() {
  return (
    <>
      <NavBar />
      <main>
        <Outlet />
      </main>
      <ChatWidget />
      <footer className="shell footer">
        <span>Campus Customs &middot; Yale Bulldog Blue &middot; New Haven, CT</span>
        <span>Officially licensed. Plainly priced.</span>
      </footer>
    </>
  );
}
