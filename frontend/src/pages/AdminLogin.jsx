import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const AdminLogin = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // OAuth2 password flow expects form urlencoded data
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    try {
      const response = await api.post("/api/v1/auth/login", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      localStorage.setItem("admin_token", response.data.access_token);
      navigate("/admin/dashboard");
    } catch (err) {
      let errMsg = "Invalid administrative credentials.";
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        errMsg = detail;
      } else if (Array.isArray(detail)) {
        errMsg = detail.map((e) => {
          const field = e.loc ? e.loc[e.loc.length - 1] : "";
          return `${field ? field.toUpperCase() + ": " : ""}${e.msg}`;
        }).join(" | ");
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="centered-container">
      <div className="glass-card register-card animate-slide-up">
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <h2 style={{ fontSize: "1.8rem", color: "var(--primary-dark)", fontWeight: "800", marginBottom: "0.25rem" }}>
            Admin Portal Login
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Entrance Examination Management System
          </p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              className="form-control"
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. admin"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              className="form-control"
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ marginTop: "1rem" }}
          >
            {loading ? "Verifying..." : "Login to Dashboard"}
          </button>
        </form>

        <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
          <button
            className="action-btn"
            onClick={() => navigate("/")}
            style={{ color: "var(--primary-light)", fontWeight: "600", fontSize: "0.9rem" }}
          >
            ← Back to Student Portal
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
