import React, { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

// ─── Anti-cheat constants ────────────────────────────────────────────────────
const MAX_VIOLATIONS = 3; // auto-submit after this many violations

const Exam = () => {
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [examName, setExamName] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [timeLeft, setTimeLeft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // ── Anti-cheat state ──────────────────────────────────────────────────────
  const [violations, setViolations] = useState(0);
  const [showWarning, setShowWarning] = useState(false);
  const [warningMessage, setWarningMessage] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);

  const timerRef = useRef(null);
  const autoSaveRef = useRef(null);
  const violationsRef = useRef(0); // ref for use inside event listeners
  const submittingRef = useRef(false);
  const attemptIdRef = useRef(null);

  // ── Helpers ───────────────────────────────────────────────────────────────

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // ── Auto-submit ───────────────────────────────────────────────────────────

  const handleAutoSubmit = useCallback(async (reason = "") => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    // Exit fullscreen gracefully before leaving page
    try { document.exitFullscreen?.(); } catch (_) {}
    try {
      const aid = attemptIdRef.current || localStorage.getItem("attempt_id");
      const response = await api.post("/api/v1/exams/submit", { attempt_id: aid });
      localStorage.setItem("submit_result", JSON.stringify(response.data));
      localStorage.removeItem("attempt_id");
      localStorage.setItem("exam_status", "submitted");
      navigate("/result");
    } catch (err) {
      console.error("Auto submit failed:", err);
      setError(
        reason
          ? `${reason} — Auto-submit failed. Please contact the administrator.`
          : "Time elapsed. Auto-submit failed. Please contact the administrator."
      );
    } finally {
      setSubmitting(false);
    }
  }, [navigate]);

  // ── Violation handler ─────────────────────────────────────────────────────

  const triggerViolation = useCallback((msg) => {
    if (submittingRef.current) return;
    violationsRef.current += 1;
    const newCount = violationsRef.current;
    setViolations(newCount);

    if (newCount >= MAX_VIOLATIONS) {
      setShowWarning(false);
      handleAutoSubmit(`Exam auto-submitted due to repeated violations (${newCount})`);
    } else {
      setWarningMessage(msg);
      setShowWarning(true);
    }
  }, [handleAutoSubmit]);

  // ── Fullscreen management ─────────────────────────────────────────────────

  const enterFullscreen = () => {
    const el = document.documentElement;
    if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
    else if (el.mozRequestFullScreen) el.mozRequestFullScreen();
    else if (el.msRequestFullscreen) el.msRequestFullscreen();
  };

  const onFullscreenChange = useCallback(() => {
    const inFS =
      !!document.fullscreenElement ||
      !!document.webkitFullscreenElement ||
      !!document.mozFullScreenElement ||
      !!document.msFullscreenElement;

    setIsFullscreen(inFS);

    if (!inFS && !submittingRef.current) {
      triggerViolation(
        "⚠️ You exited fullscreen mode! This is recorded as a violation. Do not exit fullscreen during the exam."
      );
    }
  }, [triggerViolation]);

  // ── Tab / window visibility ───────────────────────────────────────────────

  const onVisibilityChange = useCallback(() => {
    if (document.hidden && !submittingRef.current) {
      triggerViolation(
        "⚠️ Tab switch detected! Switching tabs or windows during the exam is not allowed."
      );
    }
  }, [triggerViolation]);

  const onWindowBlur = useCallback(() => {
    if (!submittingRef.current) {
      triggerViolation(
        "⚠️ Window focus lost! Switching to another application during the exam is not allowed."
      );
    }
  }, [triggerViolation]);

  // ── Keyboard blocking ─────────────────────────────────────────────────────

  const onKeyDown = useCallback((e) => {
    // Block: F12, F5, Ctrl+C, Ctrl+V, Ctrl+U, Ctrl+Shift+I, Ctrl+Shift+J, Alt+Tab, Alt+F4, Escape
    const blocked =
      e.key === "F12" ||
      e.key === "F5" ||
      (e.ctrlKey && ["c", "v", "u", "a", "s", "p"].includes(e.key.toLowerCase())) ||
      (e.ctrlKey && e.shiftKey && ["i", "j", "c"].includes(e.key.toLowerCase())) ||
      (e.altKey && e.key === "Tab") ||
      (e.altKey && e.key === "F4") ||
      e.key === "Meta" || // Windows key
      e.key === "ContextMenu";

    if (blocked) {
      e.preventDefault();
      e.stopPropagation();
    }

    // Escape exits fullscreen — re-enter silently
    if (e.key === "Escape") {
      e.preventDefault();
    }
  }, []);

  // ── Right-click blocking ──────────────────────────────────────────────────

  const onContextMenu = useCallback((e) => {
    e.preventDefault();
  }, []);

  // ── Register/unregister all anti-cheat listeners ──────────────────────────

  useEffect(() => {
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);
    document.addEventListener("mozfullscreenchange", onFullscreenChange);
    document.addEventListener("MSFullscreenChange", onFullscreenChange);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("blur", onWindowBlur);
    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("contextmenu", onContextMenu);

    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
      document.removeEventListener("mozfullscreenchange", onFullscreenChange);
      document.removeEventListener("MSFullscreenChange", onFullscreenChange);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("blur", onWindowBlur);
      document.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("contextmenu", onContextMenu);
    };
  }, [onFullscreenChange, onVisibilityChange, onWindowBlur, onKeyDown, onContextMenu]);

  // ── Load exam session ─────────────────────────────────────────────────────

  useEffect(() => {
    const sessionStr = localStorage.getItem("student_session");
    if (!sessionStr) { navigate("/"); return; }
    const studentData = JSON.parse(sessionStr);
    if (!studentData.has_verified_details) {
      navigate("/verify-details");
      return;
    }
    setStudent(studentData);

    const initExam = async () => {
      try {
        const response = await api.post("/api/v1/exams/start", {});
        const { attempt_id, exam_name, remaining_seconds, questions, answers } = response.data;
        setAttemptId(attempt_id);
        attemptIdRef.current = attempt_id;
        setExamName(exam_name);
        setTimeLeft(remaining_seconds);
        setQuestions(questions);
        setAnswers(answers || {});
        localStorage.setItem("attempt_id", attempt_id);

        // Enter fullscreen now that we have a user-gesture context (exam loaded)
        enterFullscreen();
      } catch (err) {
        let errMsg = "Error loading examination. Please contact admin.";
        const detail = err.response?.data?.detail;
        if (typeof detail === "string") errMsg = detail;
        else if (Array.isArray(detail))
          errMsg = detail.map((e) => {
            const field = e.loc ? e.loc[e.loc.length - 1] : "";
            return `${field ? field.toUpperCase() + ": " : ""}${e.msg}`;
          }).join(" | ");
        setError(errMsg);
      } finally {
        setLoading(false);
      }
    };

    initExam();

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (autoSaveRef.current) clearInterval(autoSaveRef.current);
    };
  }, [navigate]);

  // ── Countdown timer ───────────────────────────────────────────────────────

  useEffect(() => {
    if (timeLeft === null || timeLeft <= 0) {
      if (timeLeft === 0 && !submittingRef.current) handleAutoSubmit("Time elapsed");
      return;
    }
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) { clearInterval(timerRef.current); handleAutoSubmit("Time elapsed"); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [timeLeft, handleAutoSubmit]);

  // ── Manual submit ─────────────────────────────────────────────────────────

  const handleSubmitExam = async () => {
    setSubmitting(true);
    submittingRef.current = true;
    setShowConfirm(false);
    try { document.exitFullscreen?.(); } catch (_) {}
    try {
      const response = await api.post("/api/v1/exams/submit", { attempt_id: attemptId });
      localStorage.setItem("submit_result", JSON.stringify(response.data));
      localStorage.removeItem("attempt_id");
      localStorage.setItem("exam_status", "submitted");
      navigate("/result");
    } catch (err) {
      setError("Manual submission failed. Please try again.");
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Select option ─────────────────────────────────────────────────────────

  const handleSelectOption = async (questionId, option) => {
    const updatedAnswers = { ...answers, [questionId]: option };
    setAnswers(updatedAnswers);
    try {
      await api.post("/api/v1/exams/save-answer", {
        attempt_id: attemptId,
        question_id: questionId,
        selected_option: option,
      });
    } catch (err) {
      console.error("Failed to auto-save answer:", err);
    }
  };

  const handleNext = () => { if (currentIdx < questions.length - 1) setCurrentIdx(currentIdx + 1); };
  const handlePrev = () => { if (currentIdx > 0) setCurrentIdx(currentIdx - 1); };

  // ── Dismiss warning and re-enter fullscreen ───────────────────────────────

  const dismissWarning = () => {
    setShowWarning(false);
    enterFullscreen();
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="centered-container">
        <div className="spinner"></div>
      </div>
    );
  }

  if (error && questions.length === 0) {
    return (
      <div className="centered-container">
        <div className="glass-card" style={{ maxWidth: "500px", textAlign: "center" }}>
          <div className="alert alert-danger">{error}</div>
          <button className="btn btn-primary" onClick={() => navigate("/")}>Go Back to Registration</button>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentIdx];
  const progressPercent = questions.length > 0 ? ((Object.keys(answers).length / questions.length) * 100) : 0;
  const answeredCount = Object.keys(answers).filter(k => answers[k] !== null).length;

  const partNames = {
    "A": "Part A - Quantitative Ability",
    "B": "Part B - Analytical Reasoning",
    "C": "Part C - Logical Reasoning",
    "D": "Part D - Computer Awareness"
  };

  const getSectionIndex = () => {
    if (!currentQuestion || !currentQuestion.part_code) return "";
    const partQs = questions.filter(q => q.part_code === currentQuestion.part_code);
    const subsetIdx = partQs.findIndex(q => q.id === currentQuestion.id);
    return `Part ${currentQuestion.part_code}: ${subsetIdx + 1}/${partQs.length}`;
  };

  return (
    <div
      className="exam-layout animate-fade-in"
      style={{ userSelect: "none" }}   // prevent text selection
    >
      {/* ── Fullscreen reminder banner (only when out of fullscreen) ── */}
      {!isFullscreen && !showWarning && (
        <div
          style={{
            position: "fixed",
            top: 0, left: 0, right: 0,
            zIndex: 9000,
            background: "linear-gradient(90deg, #dc2626, #b91c1c)",
            color: "#fff",
            padding: "0.6rem 1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.9rem",
            fontWeight: "600",
            boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
          }}
        >
          <span>⚠️ Exam must be taken in Fullscreen mode.</span>
          <button
            onClick={enterFullscreen}
            style={{
              background: "#fff",
              color: "#dc2626",
              border: "none",
              borderRadius: "6px",
              padding: "0.35rem 1rem",
              fontWeight: "700",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            Enter Fullscreen
          </button>
        </div>
      )}

      {/* ── Anti-cheat warning modal ── */}
      {showWarning && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 99999,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: "16px",
              padding: "2.5rem",
              maxWidth: "500px",
              width: "90%",
              textAlign: "center",
              boxShadow: "0 25px 60px rgba(0,0,0,0.6)",
              border: "4px solid #dc2626",
              animation: "shake 0.4s ease",
            }}
          >
            <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>🚨</div>
            <h2 style={{ color: "#dc2626", marginBottom: "1rem", fontSize: "1.4rem" }}>
              Exam Violation Detected!
            </h2>
            <p style={{ color: "#374151", marginBottom: "1rem", lineHeight: "1.6" }}>
              {warningMessage}
            </p>
            <div
              style={{
                background: "#fef2f2",
                border: "1px solid #fca5a5",
                borderRadius: "8px",
                padding: "0.75rem 1rem",
                marginBottom: "1.5rem",
                color: "#991b1b",
                fontWeight: "600",
                fontSize: "0.9rem",
              }}
            >
              Violation {violations} of {MAX_VIOLATIONS} — Your exam will be automatically submitted after{" "}
              {MAX_VIOLATIONS} violations!
            </div>
            <button
              onClick={dismissWarning}
              style={{
                background: "linear-gradient(135deg, #1e3a8a, #3b82f6)",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                padding: "0.8rem 2rem",
                fontWeight: "700",
                fontSize: "1rem",
                cursor: "pointer",
                width: "100%",
              }}
            >
              I Understand — Return to Exam (Fullscreen)
            </button>
          </div>
        </div>
      )}

      {/* ── Questions Section ── */}
      <div className="question-panel">
        <div className="question-header">
          <span className="question-number">Question {currentIdx + 1} of {questions.length}</span>
          <span className="question-marks">Marks: {currentQuestion?.marks}</span>
        </div>

        <div className="progress-bar-container">
          <div className="progress-bar" style={{ width: `${progressPercent}%` }}></div>
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "1.5rem", textAlign: "right" }}>
          Progress: {answeredCount} / {questions.length} Answered
        </div>

        {currentQuestion && (
          <div 
            style={{ 
              background: "var(--primary-light)", 
              color: "var(--primary)", 
              padding: "0.75rem 1rem", 
              borderRadius: "8px", 
              fontWeight: "600", 
              fontSize: "0.95rem", 
              marginBottom: "1rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}
          >
            <span>{partNames[currentQuestion.part_code] || `Part ${currentQuestion.part_code}`}</span>
            <span style={{ fontSize: "0.85rem", background: "var(--primary)", color: "#fff", padding: "0.2rem 0.6rem", borderRadius: "20px" }}>
              {getSectionIndex()}
            </span>
          </div>
        )}

        {currentQuestion && (
          <>
            <div className="question-text">{currentQuestion.question_text}</div>
            {currentQuestion.image_url && (
              <div className="question-image-container" style={{ margin: "1.5rem 0", textAlign: "center" }}>
                <img 
                  src={currentQuestion.image_url} 
                  alt="Question Diagram" 
                  style={{ maxWidth: "100%", maxHeight: "350px", objectFit: "contain", borderRadius: "8px", border: "1px solid var(--border)", boxShadow: "0 4px 12px rgba(0,0,0,0.05)", padding: "0.5rem", backgroundColor: "#fff" }} 
                />
              </div>
            )}
            <div className="options-container">
              {[
                { key: "A", val: currentQuestion.option_a, img: currentQuestion.option_a_image_url },
                { key: "B", val: currentQuestion.option_b, img: currentQuestion.option_b_image_url },
                { key: "C", val: currentQuestion.option_c, img: currentQuestion.option_c_image_url },
                { key: "D", val: currentQuestion.option_d, img: currentQuestion.option_d_image_url },
              ].map((opt) => {
                const isSelected = answers[currentQuestion.id] === opt.key;
                return (
                  <div
                    key={opt.key}
                    className={`option-card ${isSelected ? "selected" : ""}`}
                    onClick={() => handleSelectOption(currentQuestion.id, opt.key)}
                  >
                    <div className="option-label">{opt.key}</div>
                    <div className="option-content-wrapper" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", width: "100%" }}>
                      {opt.val && <div className="option-text">{opt.val}</div>}
                      {opt.img && (
                        <div className="option-image-container" style={{ marginTop: "0.25rem" }}>
                          <img 
                            src={opt.img} 
                            alt={`Option ${opt.key}`} 
                            style={{ maxWidth: "100%", maxHeight: "150px", objectFit: "contain", borderRadius: "4px", border: "1px solid var(--border)" }} 
                          />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        <div className="question-navigation">
          <button
            className="btn btn-secondary"
            onClick={handlePrev}
            disabled={currentIdx === 0}
            style={{ width: "130px" }}
          >
            Previous
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleSelectOption(currentQuestion.id, null)}
            disabled={!answers[currentQuestion.id]}
            style={{ width: "130px", border: "1px solid #cbd5e1" }}
          >
            Clear Answer
          </button>
          {currentIdx === questions.length - 1 ? (
            <button className="btn btn-accent" onClick={() => setShowConfirm(true)} style={{ width: "150px" }}>
              Finish Exam
            </button>
          ) : (
            <button className="btn btn-primary" onClick={handleNext} style={{ width: "130px" }}>
              Next
            </button>
          )}
        </div>
      </div>

      {/* ── Sidebar Section ── */}
      <div className="exam-sidebar">
        {/* Timer */}
        <div className="timer-box">
          <div className="timer-title">Time Remaining</div>
          <div className={`timer-countdown ${timeLeft !== null && timeLeft < 60 ? "warning" : ""}`}>
            {timeLeft !== null ? formatTime(timeLeft) : "--:--"}
          </div>
        </div>

        {/* Violation indicator */}
        {violations > 0 && (
          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: "10px",
              padding: "0.6rem 0.75rem",
              textAlign: "center",
              color: "#dc2626",
              fontWeight: "700",
              fontSize: "0.8rem",
            }}
          >
            🚨 Violations: {violations} / {MAX_VIOLATIONS}
          </div>
        )}

        {/* Candidate info */}
        {student && (
          <div className="student-info-box">
            <div className="student-info-row">
              <span className="student-info-label">Candidate:</span>
              <span className="student-info-value">{student.name}</span>
            </div>
            <div className="student-info-row">
              <span className="student-info-label">App No:</span>
              <span className="student-info-value">{student.application_number}</span>
            </div>
            <div className="student-info-row">
              <span className="student-info-label">Degree(s):</span>
              <span className="student-info-value">
                {student.degrees
                  ? student.degrees
                      .map((d) => (d === "MSC_CS" ? "M.Sc CS" : d === "MSC_DS" ? "M.Sc DS" : d))
                      .join(", ")
                  : ""}
              </span>
            </div>
          </div>
        )}

        {/* Question Grid */}
        <div className="question-grid-box">
          <div className="grid-title">Question Grid</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {["A", "B", "C", "D"].map((pCode) => {
              const partQs = questions.filter(q => q.part_code === pCode);
              if (partQs.length === 0) return null;
              
              return (
                <div key={pCode} style={{ borderBottom: "1px dashed var(--border)", paddingBottom: "0.75rem" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "var(--primary)", marginBottom: "0.5rem" }}>
                    {partNames[pCode]}
                  </div>
                  <div className="questions-grid">
                    {partQs.map((q) => {
                      const overallIdx = questions.findIndex(item => item.id === q.id);
                      const isAnswered = !!answers[q.id];
                      const isCurrent = overallIdx === currentIdx;
                      let btnClass = "grid-btn";
                      if (isCurrent) btnClass += " current active";
                      else if (isAnswered) btnClass += " answered";
                      else btnClass += " unanswered";
                      return (
                        <button key={q.id} className={btnClass} onClick={() => setCurrentIdx(overallIdx)}>
                          {overallIdx + 1}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap", fontSize: "0.75rem" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: "10px", height: "10px", backgroundColor: "var(--primary)", borderRadius: "2px" }}></span>
              Answered
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: "10px", height: "10px", backgroundColor: "#dbeafe", border: "1px solid var(--primary-light)", borderRadius: "2px" }}></span>
              Current
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: "10px", height: "10px", backgroundColor: "var(--background)", border: "1px solid var(--border)", borderRadius: "2px" }}></span>
              Unanswered
            </span>
          </div>
        </div>

        {/* Submit button */}
        <button
          className="btn btn-accent btn-primary"
          onClick={() => setShowConfirm(true)}
          style={{ padding: "1rem" }}
        >
          Submit Exam
        </button>
      </div>

      {/* ── Submit Confirmation Modal ── */}
      {showConfirm && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "450px" }}>
            <div className="modal-header">
              <h3 className="modal-title">Submit Examination</h3>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: "1rem", fontWeight: "500" }}>Are you sure you want to end your examination?</p>
              <ul style={{ paddingLeft: "1.25rem", color: "var(--text-muted)", fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <li>Total Questions: {questions.length}</li>
                <li>Answered: {answeredCount}</li>
                <li>Remaining: {questions.length - answeredCount}</li>
              </ul>
              <p style={{ marginTop: "1.25rem", color: "var(--danger)", fontSize: "0.85rem", fontWeight: "600" }}>
                Warning: Once submitted, you cannot re-enter or change your options!
              </p>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowConfirm(false)}
                disabled={submitting}
                style={{ width: "100px" }}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleSubmitExam}
                disabled={submitting}
                style={{ width: "150px" }}
              >
                {submitting ? "Submitting..." : "Yes, Submit"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Exam;
