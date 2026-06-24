import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const Instructions = () => {
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [examInfo, setExamInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [timeLeftToStart, setTimeLeftToStart] = useState(0);

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
  }, [navigate]);

  const fetchExam = useCallback(async () => {
    try {
      const res = await api.get("/api/v1/exams/active");
      setExamInfo(res.data);
      if (res.data.exam_not_started && res.data.seconds_until_start !== undefined) {
        setTimeLeftToStart(res.data.seconds_until_start);
      } else {
        setTimeLeftToStart(0);
      }
    } catch (err) {
      setError("Error loading exam configuration. Please contact admin.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchExam();
    const intervalId = setInterval(fetchExam, 15000);
    return () => {
      clearInterval(intervalId);
    };
  }, [fetchExam]);

  useEffect(() => {
    if (timeLeftToStart <= 0) return;
    const interval = setInterval(() => {
      setTimeLeftToStart((prev) => {
        const nextVal = Math.max(0, prev - 1);
        if (nextVal === 0) {
          // Immediately fetch status when countdown hits 0
          fetchExam();
        }
        return nextVal;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [timeLeftToStart, fetchExam]);

  const formatTimeLeft = (totalSeconds) => {
    if (totalSeconds <= 0) return "00:00:00";
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const getFormattedSchedule = () => {
    if (!examInfo) return { date: "29 June 2026", time: "10:30 AM - 12:30 PM IST" };
    const startParts = examInfo.starts_at_ist ? examInfo.starts_at_ist.split(",") : [];
    const endParts = examInfo.ends_at_ist ? examInfo.ends_at_ist.split(",") : [];
    
    const date = startParts[0] || "29 June 2026";
    const startTime = startParts[1]?.trim()?.replace(" IST", "") || "10:30 AM";
    const endTime = endParts[1]?.trim() || "12:30 PM IST";
    
    return {
      date,
      time: `${startTime} - ${endTime}`
    };
  };

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
      
      const isNotStarted = (err.response?.status === 403 && (err.response?.data?.exam_not_started || (detail && typeof detail === "object" && detail.exam_not_started)));
      
      if (isNotStarted) {
        errMsg = "Exam has not started yet. Please wait until 10:30 AM IST.";
        const secs = detail && typeof detail === "object" ? detail.seconds_until_start : err.response?.data?.seconds_until_start;
        if (secs !== undefined) {
          setTimeLeftToStart(secs);
        }
      } else if (typeof detail === "string") {
        errMsg = detail;
      } else if (typeof detail === "object" && detail !== null && detail.detail) {
        errMsg = detail.detail;
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

  const isStartButtonDisabled = !agreed || loading || timeLeftToStart > 0 || (examInfo && !examInfo.is_start_allowed);
  const schedule = getFormattedSchedule();

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

        {timeLeftToStart > 0 && (
          <div className="alert alert-warning" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <span><strong>Exam Status:</strong> Waiting for official start time.</span>
            <span style={{ fontSize: "1.1rem", fontWeight: "800", letterSpacing: "1px" }}>
              Exam starts in {formatTimeLeft(timeLeftToStart)}
            </span>
          </div>
        )}

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
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Exam Date:</span>
                <p style={{ fontWeight: "600", fontSize: "1.1rem" }}>{schedule.date}</p>
              </div>
              <div>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Exam Time:</span>
                <p style={{ fontWeight: "600", fontSize: "1.1rem", color: "var(--primary)" }}>
                  {schedule.time}
                </p>
              </div>
            </div>
          </div>
        )}

        <ul className="instructions-list">
          <li><strong>Official Schedule:</strong> The examination is scheduled for <strong>June 29, 2026</strong>. The duration is <strong>120 minutes (2 hours)</strong> containing <strong>100 questions</strong>.</li>
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
            disabled={isStartButtonDisabled}
            style={{ flexGrow: "1" }}
          >
            {loading ? "Starting..." : timeLeftToStart > 0 ? `Exam starts in ${formatTimeLeft(timeLeftToStart)}` : "I am ready, Start Exam"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Instructions;
