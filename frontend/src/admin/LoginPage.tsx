import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { ApiError } from "../api";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { email, login } = useAuth();
  const navigate = useNavigate();
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (email) return <Navigate to="/admin/documenti" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(address, password);
      navigate("/admin/documenti", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Troppi tentativi. Riprova tra qualche minuto."
          : "Email o password non corrette.",
      );
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="admin-login">
      <form className="card admin-login__form" onSubmit={onSubmit}>
        <h1>Area riservata</h1>
        <label>
          Email
          <input type="email" autoComplete="username" value={address} onChange={(e) => setAddress(e.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button button--primary" disabled={busy}>
          {busy ? "Accesso…" : "Accedi"}
        </button>
      </form>
    </main>
  );
}
