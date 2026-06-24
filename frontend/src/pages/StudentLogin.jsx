import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import api from "../api";

const StudentLogin = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  const [formData, setFormData] = useState({
    application_number: "",
    mobile_number: "",
  });
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [examActive, setExamActive] = useState(true);

  useEffect(() => {
    // Check if redirect state has a message
    if (location.state && location.state.message) {
      setError(location.state.message);
      // Clear location state so the message doesn't persist on manual refresh
      navigate(location.pathname, { replace: true, state: {} });
    }

    // Check if exam is active
    api.get("/api/v1/exams/active")
      .then((res) => {
        if (res.data.exam_not_started) {
          setExamActive(true);
          setInfoMessage(`The entrance examination will start at ${res.data.starts_at_ist || "29 June 2026, 10:30 AM IST"}. You can login and verify your details now.`);
        } else if (!res.data.is_login_allowed) {
          setExamActive(false);
          setError("The entrance examination is not active at this time.");
        } else {
          setExamActive(true);
          setInfoMessage("");
        }
      })
      .catch((err) => {
        console.error("Error checking exam status:", err);
      });
  }, [location, navigate]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");
    setLoading(true);

    if (!formData.application_number.trim() || !formData.mobile_number.trim()) {
      setError("Please fill in all fields.");
      setLoading(false);
      return;
    }

    try {
      const response = await api.post("/api/v1/students/login", {
        application_number: formData.application_number.trim(),
        mobile_number: formData.mobile_number.trim(),
      });

      const { access_token, candidate, applications, attempt_status, attempt_id } = response.data;
      
      // Store session and token securely
      localStorage.setItem("student_token", access_token);
      localStorage.setItem("student_session", JSON.stringify(candidate));
      localStorage.setItem("student_applications", JSON.stringify(applications));
      localStorage.setItem("exam_status", attempt_status);
      
      if (attempt_id) {
        localStorage.setItem("attempt_id", attempt_id);
      } else {
        localStorage.removeItem("attempt_id");
      }

      // Check detail verification status
      if (!candidate.has_verified_details) {
        navigate("/verify-details");
      } else if (attempt_status === "submitted") {
        navigate("/result");
      } else if (attempt_status === "resume") {
        navigate("/exam");
      } else {
        navigate("/instructions");
      }
    } catch (err) {
      let errMsg = "Login failed. Please verify your credentials.";
      if (err.response && err.response.data && err.response.data.detail) {
        errMsg = err.response.data.detail;
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="centered-container">
      <div className="glass-card register-card animate-slide-up" style={{ maxWidth: "480px" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <h2 style={{ fontSize: "1.8rem", color: "var(--primary)", fontWeight: "800", marginBottom: "0.25rem" }}>
            Candidate Login
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Periyar University PG Entrance Examination Portal
          </p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {infoMessage && <div className="alert alert-info">{infoMessage}</div>}
        {successMessage && <div className="alert alert-success">{successMessage}</div>}

        {!examActive && (
          <div className="alert alert-info" style={{ marginBottom: "0" }}>
            The exam session is currently closed. If you are an administrator, please log in to configuration settings.
          </div>
        )}

        {examActive && (
          <form onSubmit={handleSubmit}>
            <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
              <div className="form-group">
                <label className="form-label" htmlFor="application_number">Application Number</label>
                <input
                  className="form-control"
                  type="text"
                  id="application_number"
                  name="application_number"
                  placeholder="e.g. PU202610234"
                  value={formData.application_number}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="mobile_number">Mobile Number</label>
                <input
                  className="form-control"
                  type="tel"
                  id="mobile_number"
                  name="mobile_number"
                  placeholder="Registered 10-digit mobile number"
                  value={formData.mobile_number}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>

            <button
              className="btn btn-primary animate-pulse"
              type="submit"
              disabled={loading}
              style={{ marginTop: "2rem", width: "100%" }}
            >
              {loading ? "Logging in..." : "Login & Proceed"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default StudentLogin;
