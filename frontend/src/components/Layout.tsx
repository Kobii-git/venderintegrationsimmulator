import { Link, Outlet, useLocation } from "react-router-dom";

export function Layout() {
  const location = useLocation();

  const isActive = (path: string) =>
    path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(path);

  return (
    <div className="layout">
      <header className="topbar">
        <Link to="/" className="topbar-brand">
          Integration Simulator
        </Link>
        <nav className="topbar-nav">
          <Link
            to="/"
            className={
              isActive("/") && !location.pathname.startsWith("/simulations/new")
                ? "active"
                : ""
            }
          >
            Simulations
          </Link>
          <Link
            to="/simulations/new"
            className={isActive("/simulations/new") ? "active" : ""}
          >
            New Simulation
          </Link>
          <Link to="/lab" className={isActive("/lab") ? "active" : ""}>
            Log Lab
          </Link>
          <Link
            to="/inbound-requests"
            className={isActive("/inbound-requests") ? "active" : ""}
          >
            Inbound Requests
          </Link>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
