import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const Instructions = () => {
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [examInfo, setExamInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    // Check if student is registered
    const sessionStr = localStorage.getItem("student_session");
    if (!sessionStr) {
      navigate("/");
      return;
    }
    const cand = JSON.parse(sessionStr);
    if (!cand.has_verified_details) {
      navigate("/verify-details");
      return;
    }
    setStudent(cand);

    // Fetch active exam information
    api.get("/api/v1/exams/active")
      .then((res) => {
        setExamInfo(res.data);
      })
      .catch((err) => {
        setError("Error loading exam configuration. Please contact admin.");
        console.error(err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [navigate]);

  const handleStartExam = async () => {
    if (!agreed) return;
    setError("");
    setLoading(true);

    try {
      const response = await api.post("/api/v1/exams/start", {});

      // Save attempt metadata
      localStorage.setItem("attempt_id", response.data.attempt_id);
      localStorage.setItem("exam_status", "in_progress");
      
      // Navigate to examination panel
      navigate("/exam");
    } catch (err) {
      let errMsg = "Could not start exam. Please try again.";
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
      setLoading(false);
    }
  };

  if (loading && !examInfo) {
    return (
      <div className="centered-container">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="centered-container">
      <div className="glass-card instructions-container animate-slide-up">
        <h2 style={{ color: "var(--primary)", fontWeight: "800", marginBottom: "1rem" }}>
          General Instructions
        </h2>
        <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
          Please read the instructions carefully before commencing the examination:
        </p>

        {error && <div className="alert alert-danger">{error}</div>}

        {examInfo && (
          <div style={{ backgroundColor: "#f8fafc", padding: "1.25rem", borderRadius: "var(--radius-md)", marginBottom: "1.5rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: "700", marginBottom: "0.75rem", color: "var(--primary-dark)" }}>
              Exam Summary: {examInfo.name}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
              <div>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Duration:</span>
                <p style={{ fontWeight: "600", fontSize: "1.1rem" }}>{examInfo.duration_minutes} Minutes</p>
              </div>
              <div>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Total Questions:</span>
                <p style={{ fontWeight: "600", fontSize: "1.1rem" }}>{examInfo.total_questions} MCQs</p>
              </div>
              <div>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Negative Marking:</span>
                <p style={{ fontWeight: "600", fontSize: "1.1rem", color: "var(--success)" }}>
                  Nil
                </p>
              </div>
            </div>
          </div>
        )}

        <ul className="instructions-list">
          <li><strong>Single Attempt Only:</strong> You cannot attempt the test twice with the same Application Number.</li>
          <li><strong>Auto-Save Progress:</strong> Your selected answers are updated automatically and saved securely in real-time. If you lose internet connectivity or refresh, you can resume.</li>
          <li><strong>Timer Auto-Submission:</strong> Once the timer hits zero, your exam will submit automatically, and no further edits will be recorded.</li>
          <li><strong>Disqualification:</strong> Attempting to navigate away, open other tabs, or refresh might disrupt your connection. Ensure a stable internet connection.</li>
          <li><strong>Result:</strong> Upon submitting, your final score dashboard will be rendered immediately.</li>
        </ul>

        <div style={{ margin: "2rem 0 1rem 0", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <input
            type="checkbox"
            id="agree-checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            style={{ width: "18px", height: "18px", cursor: "pointer" }}
          />
          <label htmlFor="agree-checkbox" style={{ fontSize: "0.95rem", fontWeight: "500", cursor: "pointer" }}>
            I have read and understood all instructions and agree to abide by them.
          </label>
        </div>

        <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
          <button
            className="btn btn-secondary"
            onClick={() => navigate("/")}
            style={{ width: "150px" }}
          >
            Go Back
          </button>
          <button
            className="btn btn-primary"
            onClick={handleStartExam}
            disabled={!agreed || loading}
            style={{ flexGrow: "1" }}
          >
            {loading ? "Starting..." : "I am ready, Start Exam"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Instructions;
