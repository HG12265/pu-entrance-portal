import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const Result = () => {
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const token = localStorage.getItem("student_token");
        if (!token) {
          navigate("/");
          return;
        }
        
        const response = await api.get("/api/v1/results/my-results");
        if (response.data.has_results) {
          setResult(response.data);
        } else {
          // No results found, check exam status to redirect
          const examStatus = localStorage.getItem("exam_status") || "new";
          if (examStatus === "resume") {
            navigate("/exam");
          } else {
            navigate("/instructions");
          }
        }
      } catch (err) {
        console.error("Error loading results:", err);
        setError("Failed to load your examination results. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    const resStr = localStorage.getItem("submit_result");
    if (resStr) {
      const storedResult = JSON.parse(resStr);
      setResult(storedResult);
      // Fetch rankings/latest details anyway to show ranks & counselling status
      fetchResults();
    } else {
      fetchResults();
    }
  }, [navigate]);

  const handleFinish = () => {
    localStorage.removeItem("student_token");
    localStorage.removeItem("student_session");
    localStorage.removeItem("student_applications");
    localStorage.removeItem("exam_status");
    localStorage.removeItem("attempt_id");
    localStorage.removeItem("submit_result");
    navigate("/");
  };

  if (loading && !result) {
    return (
      <div className="centered-container">
        <div className="spinner"></div>
      </div>
    );
  }

  // Helper to map DB codes to display titles
  const mapDegreeCode = (code) => {
    const maps = {
      "MCA": "MCA",
      "MSC_CS": "M.Sc Computer Science",
      "MSC_DS": "M.Sc Data Science"
    };
    return maps[code] || code;
  };

  return (
    <div className="centered-container" style={{ padding: "2rem 1rem" }}>
      <div className="glass-card results-container animate-slide-up" style={{ textAlign: "center", maxWidth: "600px", width: "100%" }}>
        <h2 style={{ color: "var(--primary)", fontWeight: "800", marginBottom: "0.5rem" }}>
          Exam Submitted Successfully
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginBottom: "1.5rem" }}>
          Thank you for taking the Periyar University Entrance Examination.
        </p>

        {error && <div className="alert alert-danger">{error}</div>}

        {result && (
          <>
            {/* Student Information Details Block */}
            <div style={{ backgroundColor: "#f8fafc", padding: "1.25rem", borderRadius: "var(--radius-md)", textAlign: "left", marginBottom: "1.5rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "0.5rem", fontSize: "0.95rem" }}>
                <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Application No:</span>
                <span style={{ fontWeight: "700", color: "var(--primary)" }}>{result.application_number || (result.rankings && result.rankings.length > 0 ? result.rankings[0].application_number : "")}</span>

                <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Student Name:</span>
                <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{result.candidate_name || result.student_name}</span>

                <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Degree Applied:</span>
                <span style={{ fontWeight: "600", color: "var(--text-main)" }}>
                  {result.degrees ? result.degrees.map(mapDegreeCode).join(", ") : (result.rankings ? result.rankings.map(r => mapDegreeCode(r.course_code)).join(", ") : "")}
                </span>
              </div>
            </div>

            {result.result_visibility ? (
              <div>
                <div className="score-badge">
                  <span className="score-num">{result.score}</span>
                  <span className="score-lbl">Exam Marks Obtained</span>
                </div>

                <div style={{
                  backgroundColor: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  padding: "1rem",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "1.5rem",
                  textAlign: "left"
                }}>
                  <h4 style={{ color: "#166534", fontWeight: "700", fontSize: "0.95rem", marginBottom: "0.75rem", borderBottom: "1px solid #dcfce7", paddingBottom: "0.25rem" }}>
                    Final Score Calculation Breakdown (50% UG + 50% Entrance)
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.9rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-muted)" }}>Entrance Mark:</span>
                      <span style={{ fontWeight: "600" }}>{result.score} / {result.entrance_total_marks || 100}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-muted)" }}>Entrance 50%:</span>
                      <span style={{ fontWeight: "600" }}>{result.entrance_weighted_score}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-muted)" }}>UG Percentage:</span>
                      <span style={{ fontWeight: "600" }}>{result.ug_percentage !== null && result.ug_percentage !== undefined ? `${result.ug_percentage}%` : "Incomplete"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-muted)" }}>UG 50%:</span>
                      <span style={{ fontWeight: "600" }}>{result.ug_weighted_score}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px dashed #bbf7d0", paddingTop: "0.5rem", marginTop: "0.25rem" }}>
                      <span style={{ fontWeight: "700", color: "#166534" }}>Final Score:</span>
                      <span style={{ fontWeight: "800", color: "#166534", fontSize: "1.1rem" }}>{result.final_score !== null && result.final_score !== undefined ? `${result.final_score} / 100` : "Incomplete"}</span>
                    </div>
                  </div>
                </div>

                <div className="results-stats-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem" }}>
                  <div className="result-stat-card" style={{ padding: "0.75rem 0.25rem" }}>
                    <div className="result-stat-val" style={{ fontSize: "1.2rem" }}>{result.total_questions}</div>
                    <div className="result-stat-lbl" style={{ fontSize: "0.75rem" }}>Total Qns</div>
                  </div>
                  <div className="result-stat-card" style={{ padding: "0.75rem 0.25rem" }}>
                    <div className="result-stat-val" style={{ fontSize: "1.2rem", color: "var(--primary)" }}>{result.attempted_questions}</div>
                    <div className="result-stat-lbl" style={{ fontSize: "0.75rem" }}>Attempted</div>
                  </div>
                  <div className="result-stat-card" style={{ padding: "0.75rem 0.25rem" }}>
                    <div className="result-stat-val" style={{ fontSize: "1.2rem", color: "var(--success)" }}>{result.correct_answers}</div>
                    <div className="result-stat-lbl" style={{ fontSize: "0.75rem" }}>Correct</div>
                  </div>
                  <div className="result-stat-card" style={{ padding: "0.75rem 0.25rem" }}>
                    <div className="result-stat-val" style={{ fontSize: "1.2rem", color: "var(--danger)" }}>{result.wrong_answers}</div>
                    <div className="result-stat-lbl" style={{ fontSize: "0.75rem" }}>Wrong</div>
                  </div>
                  <div className="result-stat-card" style={{ padding: "0.75rem 0.25rem" }}>
                    <div className="result-stat-val" style={{ fontSize: "1.2rem" }}>{result.percentage}%</div>
                    <div className="result-stat-lbl" style={{ fontSize: "0.75rem" }}>Exam %</div>
                  </div>
                </div>

                {result.rankings && result.rankings.length > 0 && (
                  <div style={{ marginTop: "2rem", textAlign: "left" }}>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)", borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                      Counselling & Course Rankings
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                      {result.rankings.map((r, i) => {
                        let badgeColor = "var(--text-muted)";
                        let badgeBg = "#f1f5f9";
                        if (r.confirmation_status === "Confirmed") {
                          badgeColor = "#166534";
                          badgeBg = "#dcfce7";
                        } else if (r.confirmation_status === "Eligible") {
                          badgeColor = "#1e3a8a";
                          badgeBg = "#dbeafe";
                        } else if (r.confirmation_status === "Waitlisted") {
                          badgeColor = "#854d0e";
                          badgeBg = "#fef9c3";
                        } else if (r.confirmation_status === "Excluded") {
                          badgeColor = "#991b1b";
                          badgeBg = "#fee2e2";
                        }

                        return (
                          <div key={i} style={{ backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                              <span style={{ fontWeight: "700", color: "var(--primary)" }}>{r.course_name} ({r.course_code})</span>
                              <span style={{ fontSize: "0.85rem", fontWeight: "700", color: badgeColor, backgroundColor: badgeBg, padding: "0.25rem 0.6rem", borderRadius: "12px" }}>
                                {r.confirmation_status}
                              </span>
                            </div>
                            
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.9rem" }}>
                              <div>
                                <span style={{ color: "var(--text-muted)" }}>Original Rank: </span>
                                <span style={{ fontWeight: "600" }}>{r.original_rank}</span>
                              </div>
                              <div>
                                <span style={{ color: "var(--text-muted)" }}>Active Rank: </span>
                                <span style={{ fontWeight: "600" }}>{r.active_rank === -1 ? "N/A (Excluded)" : r.active_rank}</span>
                              </div>
                            </div>
                            {r.excluded_reason && (
                              <div style={{ fontSize: "0.85rem", color: "#b91c1c", marginTop: "0.5rem", fontWeight: "500" }}>
                                Reason: {r.excluded_reason}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="alert alert-info" style={{ margin: "2rem 0", textAlign: "left" }}>
                <h4 style={{ fontWeight: "700", marginBottom: "0.5rem" }}>Results Visibility Notice</h4>
                Your answers have been saved and evaluated. The detailed marks, statistics, and scores will be made visible online after the university concludes all examination windows. Please keep checking the official notifications.
              </div>
            )}
          </>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "2rem" }}>
          <button
            className="btn btn-secondary"
            onClick={handleFinish}
          >
            Return to Portal Home
          </button>
        </div>
      </div>
    </div>
  );
};

export default Result;
