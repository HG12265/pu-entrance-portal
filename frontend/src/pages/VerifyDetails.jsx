import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const VerifyDetails = () => {
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [applications, setApplications] = useState([]);
  const [confirmDetails, setConfirmDetails] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("student_token");
    const candidateStr = localStorage.getItem("student_session");
    const appsStr = localStorage.getItem("student_applications");

    if (!token || !candidateStr) {
      navigate("/");
      return;
    }

    const candidateObj = JSON.parse(candidateStr);
    setCandidate(candidateObj);
    if (candidateObj && candidateObj.applications && candidateObj.applications.length > 0) {
      setApplications(candidateObj.applications);
    } else if (appsStr) {
      setApplications(JSON.parse(appsStr));
    }
  }, [navigate]);

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!confirmDetails) {
      setError("Please check the confirmation box to proceed.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await api.post("/api/v1/students/verify-details", {
        confirm_details: true,
      });

      // Update candidate details in local storage
      const updatedCandidate = { ...candidate, has_verified_details: true };
      localStorage.setItem("student_session", JSON.stringify(updatedCandidate));

      const attemptStatus = localStorage.getItem("exam_status") || "new";

      if (attemptStatus === "submitted") {
        navigate("/result");
      } else if (attemptStatus === "resume") {
        navigate("/exam");
      } else {
        navigate("/instructions");
      }
    } catch (err) {
      let errMsg = "Verification failed. Please try again or contact support.";
      if (err.response && err.response.data && err.response.data.detail) {
        errMsg = err.response.data.detail;
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  if (!candidate) {
    return (
      <div className="centered-container">
        <div className="spinner"></div>
      </div>
    );
  }

  // Helper to map DB codes to display titles
  const mapDegreeCode = (code) => {
    const maps = {
      "MCA": "Master of Computer Applications (MCA)",
      "MSC_CS": "M.Sc Computer Science (MSC_CS)",
      "MSC_DS": "M.Sc Data Science (MSC_DS)"
    };
    return maps[code] || code;
  };

  return (
    <div className="centered-container">
      <div className="glass-card instructions-container animate-slide-up" style={{ maxWidth: "650px" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <h2 style={{ color: "var(--primary)", fontWeight: "800", marginBottom: "0.25rem" }}>
            Verify Your Details
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Periyar University PG Entrance Examination
          </p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        <div style={{ backgroundColor: "#f8fafc", padding: "1.5rem", borderRadius: "var(--radius-md)", marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)", borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
            Candidate Profile Information
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: "0.8rem", fontSize: "0.95rem" }}>
            <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Full Name:</span>
            <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{candidate.full_name}</span>

            <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Mobile Number:</span>
            <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{candidate.mobile_number}</span>

            <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Email Address:</span>
            <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{candidate.email || "N/A"}</span>

            <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Community:</span>
            <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{candidate.community || "OC"}</span>

            <span style={{ fontWeight: "600", color: "var(--text-muted)" }}>Date of Birth:</span>
            <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{candidate.date_of_birth || "N/A"}</span>
          </div>
        </div>

        <div style={{ backgroundColor: "#f8fafc", padding: "1.5rem", borderRadius: "var(--radius-md)", marginBottom: "2rem" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)", borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
            Applied Courses / Applications
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {applications.map((app) => (
              <div 
                key={app.id} 
                style={{ 
                  backgroundColor: "#fff", 
                  padding: "1rem", 
                  borderRadius: "var(--radius-sm)", 
                  border: "1px solid #e2e8f0",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                  gap: "0.5rem",
                  fontSize: "0.9rem"
                }}
              >
                <div>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>Application No</span>
                  <span style={{ fontWeight: "700", color: "var(--primary)" }}>{app.application_number}</span>
                </div>
                <div>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>Course</span>
                  <span style={{ fontWeight: "600" }}>{app.course_name || mapDegreeCode(app.course_code)}</span>
                </div>
                {app.quota && (
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>Quota</span>
                    <span style={{ fontWeight: "600" }}>{app.quota}</span>
                  </div>
                )}
                <div>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>UG Percentage</span>
                  <span style={{ fontWeight: "600" }}>{app.ug_marks !== null && app.ug_marks !== undefined ? `${app.ug_marks}%` : "N/A"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <form onSubmit={handleVerify}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", marginBottom: "2rem" }}>
            <input
              type="checkbox"
              id="confirm-details-checkbox"
              checked={confirmDetails}
              onChange={(e) => setConfirmDetails(e.target.checked)}
              style={{ width: "18px", height: "18px", marginTop: "3px", cursor: "pointer" }}
            />
            <label htmlFor="confirm-details-checkbox" style={{ fontSize: "0.95rem", fontWeight: "500", cursor: "pointer", lineHeight: "1.4" }}>
              I hereby confirm that all the details displayed above are correct and belong to me. I understand that I cannot edit these details after confirming.
            </label>
          </div>

          <div style={{ display: "flex", gap: "1rem" }}>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => {
                localStorage.clear();
                navigate("/");
              }}
              style={{ width: "150px" }}
            >
              Logout
            </button>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={!confirmDetails || loading}
              style={{ flexGrow: "1" }}
            >
              {loading ? "Confirming..." : "Confirm & Proceed"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default VerifyDetails;
