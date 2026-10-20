import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Icon } from "./Icon";

const groups = [
  { label: "Workspace", links: [
    { to: "/", label: "Simulations", icon: "layers" as const },
    { to: "/lab", label: "Log Lab", icon: "lab" as const },
  ] },
  { label: "Tools", links: [
    { to: "/raw-logs", label: "Generate raw log", icon: "code" as const },
    { to: "/uploads", label: "Upload logs", icon: "upload" as const },
  ] },
  { label: "Inspect & learn", links: [
    { to: "/inbound-requests", label: "Inbound Requests", icon: "activity" as const },
    { to: "/guides", label: "Deployment Guides", icon: "book" as const },
  ] },
];

export function Layout() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => { setMenuOpen(false); }, [location.pathname, location.search]);

  return (
    <div className="layout" onKeyDown={(event) => {
      if (event.key === "Escape" && menuOpen) {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    }}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="mobile-topbar">
        <Link to="/" className="mobile-brand">Integration Simulator</Link>
        <button type="button" className="btn" ref={menuButton} aria-expanded={menuOpen}
          aria-controls="app-sidebar" onClick={() => setMenuOpen(!menuOpen)}>
          <Icon name={menuOpen ? "close" : "menu"} />{menuOpen ? "Close menu" : "Menu"}
        </button>
      </header>
      <aside className={`sidebar ${menuOpen ? "is-open" : ""}`} id="app-sidebar">
        <Link to="/" className="sidebar-brand">
          <span className="brand-mark"><Icon name="layers" /></span>
          <span>Integration<span className="brand-second-line">Simulator</span></span>
        </Link>
        <nav aria-label="Main navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-group-label">{group.label}</p>
              {group.links.map((link) => {
                const active = link.to === "/"
                  ? location.pathname === "/" || location.pathname.startsWith("/simulations")
                  : location.pathname.startsWith(link.to);
                return (
                  <Link key={link.to} to={link.to} aria-current={active ? "page" : undefined}
                    onClick={() => {
                      if (menuOpen) requestAnimationFrame(() => document.getElementById("main-content")?.focus());
                    }} className={`nav-link ${active ? "active" : ""}`}>
                    <Icon name={link.icon} />{link.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="brand-dot" />Your integration workspace</div>
      </aside>
      <div className="workspace">
        <div className="workspace-bar"><span>Integration workspace</span><span className="workspace-context">Configure · Test · Inspect</span></div>
        <main className="main" id="main-content" tabIndex={-1}><Outlet /></main>
      </div>
    </div>
  );
}
