import { Navigate, NavLink, Outlet, useNavigate } from "react-router";
import { useAuth } from "./AuthContext";

export function AdminLayout() {
  const { email, loading, logout } = useAuth();
  const navigate = useNavigate();

  if (loading) return <p className="admin-loading">Caricamento…</p>;
  if (!email) return <Navigate to="/admin/login" replace />;

  async function onLogout() {
    await logout();
    navigate("/admin/login", { replace: true });
  }

  return (
    <div className="admin">
      <aside className="admin__sidebar">
        <p className="admin__brand">Assistente NCC · Admin</p>
        <nav aria-label="Area admin">
          <NavLink to="/admin/documenti">Documenti</NavLink>
          <NavLink to="/admin/conversazioni">Conversazioni</NavLink>
          <NavLink to="/admin/domande">Domande senza risposta</NavLink>
          <NavLink to="/">Chat demo ↗</NavLink>
        </nav>
        <div className="admin__user">
          <span title={email}>{email}</span>
          <button type="button" className="button" onClick={() => void onLogout()}>
            Esci
          </button>
        </div>
      </aside>
      <main className="admin__content">
        <Outlet />
      </main>
    </div>
  );
}
