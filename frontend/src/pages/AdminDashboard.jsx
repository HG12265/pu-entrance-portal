import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { 
  LayoutDashboard, 
  Users, 
  BookOpen, 
  Settings, 
  FileSpreadsheet, 
  LogOut, 
  Plus, 
  Edit, 
  Trash2, 
  Upload, 
  Search, 
  FileDown, 
  CheckCircle,
  XCircle,
  Clock,
  Award,
  Trophy,
  ShieldCheck
} from "lucide-react";

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("overview");
  const [stats, setStats] = useState(null);
  
  // Student Applications states
  const [applications, setApplications] = useState([]);
  const [courses, setCourses] = useState([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [appUploadFile, setAppUploadFile] = useState(null);
  const [appUploadResult, setAppUploadResult] = useState(null);
  const [appSearch, setAppSearch] = useState("");
  
  // Question states
  const [questions, setQuestions] = useState([]);
  const [questionModal, setQuestionModal] = useState({ show: false, editId: null });
  const [questionForm, setQuestionForm] = useState({
    question_text: "",
    option_a: "",
    option_b: "",
    option_c: "",
    option_d: "",
    correct_option: "A",
    marks: 1.0,
    image_url: "",
    option_a_image_url: "",
    option_b_image_url: "",
    option_c_image_url: "",
    option_d_image_url: "",
    part_code: "A",
    source_s_no: ""
  });
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [questionPartFilter, setQuestionPartFilter] = useState("All");
  
  // Settings states
  const [examSettings, setExamSettings] = useState({
    name: "",
    total_questions: 30,
    duration_minutes: 30,
    start_date: "",
    end_date: "",
    result_visibility: true
  });
  const [editingCourseId, setEditingCourseId] = useState(null);
  const [editSeatCount, setEditSeatCount] = useState(30);
  const [communitySeats, setCommunitySeats] = useState([]);
  const [editCommunitySeats, setEditCommunitySeats] = useState({});

  // Counselling & Rankings states
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardSearch, setLeaderboardSearch] = useState("");
  const [leaderboardDegree, setLeaderboardDegree] = useState("MCA");
  const [leaderboardCommunity, setLeaderboardCommunity] = useState("All");
  const [showExcluded, setShowExcluded] = useState(true);

  // Attempts & Reopen states
  const [attemptSearchQuery, setAttemptSearchQuery] = useState("");
  const [attemptSearchResults, setAttemptSearchResults] = useState(null);
  const [reopenModal, setReopenModal] = useState({ show: false, attemptId: null, candidateName: "", reason: "", timeExtension: 0 });
  const [forceSubmitModal, setForceSubmitModal] = useState({ show: false, attemptId: null, candidateName: "", reason: "" });

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });

  useEffect(() => {
    loadOverview();
    loadCourses();
  }, []);

  const loadOverview = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/v1/auth/dashboard-stats");
      setStats(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoading(false);
    }
  };

  const loadCourses = async () => {
    try {
      const res = await api.get("/api/v1/auth/courses");
      setCourses(res.data);
      if (res.data.length > 0 && !selectedCourseId) {
        setSelectedCourseId(res.data[0].id.toString());
      }
    } catch (err) {
      console.error("Error loading courses:", err);
    }
  };

  const loadStudentApplications = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/v1/students/applications");
      setApplications(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApiError = (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("admin_token");
      navigate("/admin/login");
    } else {
      let errorText = "An unexpected error occurred.";
      const detail = err.response?.data?.detail;
      if (detail) {
        if (typeof detail === "string") {
          errorText = detail;
        } else if (typeof detail === "object") {
          if (detail.message) {
            errorText = detail.message;
            if (detail.errors && Array.isArray(detail.errors)) {
              errorText += " | Details: " + detail.errors.join(" | ");
            }
          } else {
            errorText = JSON.stringify(detail);
          }
        }
      }
      setMessage({
        text: errorText,
        type: "danger"
      });
    }
  };

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: "", type: "" }), 5000);
  };

  // Helper to map DB codes to display titles
  const mapDegreeCode = (code) => {
    const maps = {
      "MCA": "MCA",
      "MSC_CS": "M.Sc Computer Science",
      "MSC_DS": "M.Sc Data Science"
    };
    return maps[code] || code;
  };

  // ---------------- APPLICATIONS MODULE ----------------
  const handleExcelApplicationsUpload = async (e) => {
    e.preventDefault();
    if (!appUploadFile) {
      showMessage("Please select an Excel or CSV file.", "danger");
      return;
    }
    if (!selectedCourseId) {
      showMessage("Please select a course for the application batch.", "danger");
      return;
    }
    setActionLoading(true);
    setAppUploadResult(null);

    const formData = new FormData();
    formData.append("file", appUploadFile);

    try {
      const res = await api.post(`/api/v1/auth/applications/upload?course_id=${selectedCourseId}`, formData, {
        headers: {
          "Content-Type": "multipart/form-data"
        }
      });
      setAppUploadResult(res.data);
      if (res.data.status === "success" || res.data.status === "partial_success") {
        showMessage(`Successfully processed Excel sheet. ${res.data.inserted_count} added, ${res.data.updated_count} updated.`);
        loadStudentApplications();
        loadOverview();
      } else {
        showMessage("Excel upload failed due to formatting or structural errors.", "danger");
      }
    } catch (err) {
      if (err.response?.status === 400 && err.response?.data?.detail?.detected_columns) {
        setAppUploadResult({
          status: "error",
          ...err.response.data.detail
        });
        showMessage(err.response.data.detail.message || "Required columns are missing.", "danger");
      } else {
        handleApiError(err);
      }
    } finally {
      setActionLoading(false);
    }
  };

  // ---------------- QUESTIONS BANK MODULE ----------------
  const loadQuestions = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/v1/questions");
      setQuestions(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAddQuestion = () => {
    setQuestionForm({
      question_text: "",
      option_a: "",
      option_b: "",
      option_c: "",
      option_d: "",
      correct_option: "A",
      marks: 1.0,
      image_url: "",
      option_a_image_url: "",
      option_b_image_url: "",
      option_c_image_url: "",
      option_d_image_url: "",
      part_code: "A",
      source_s_no: ""
    });
    setQuestionModal({ show: true, editId: null });
  };

  const handleOpenEditQuestion = (q) => {
    setQuestionForm({
      question_text: q.question_text,
      option_a: q.option_a,
      option_b: q.option_b,
      option_c: q.option_c,
      option_d: q.option_d,
      correct_option: q.correct_option,
      marks: q.marks,
      image_url: q.image_url || "",
      option_a_image_url: q.option_a_image_url || "",
      option_b_image_url: q.option_b_image_url || "",
      option_c_image_url: q.option_c_image_url || "",
      option_d_image_url: q.option_d_image_url || "",
      part_code: q.part_code || "A",
      source_s_no: q.source_s_no !== null && q.source_s_no !== undefined ? q.source_s_no : ""
    });
    setQuestionModal({ show: true, editId: q.id });
  };

  const handleImageUpload = async (file, field) => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setActionLoading(true);
    try {
      const res = await api.post("/api/v1/questions/upload-image", formData, {
        headers: {
          "Content-Type": "multipart/form-data"
        }
      });
      setQuestionForm(prev => ({
        ...prev,
        [field]: res.data.url
      }));
    } catch (err) {
      alert("Failed to upload image: " + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveQuestion = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    const payload = {
      ...questionForm,
      source_s_no: questionForm.source_s_no !== "" ? parseInt(questionForm.source_s_no, 10) : null
    };
    try {
      if (questionModal.editId) {
        await api.put(`/api/v1/questions/${questionModal.editId}`, payload);
        showMessage("Question updated successfully.");
      } else {
        await api.post("/api/v1/questions", payload);
        showMessage("Question created successfully.");
      }
      setQuestionModal({ show: false, editId: null });
      loadQuestions();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteQuestion = async (id) => {
    if (!window.confirm("Are you sure you want to delete this question?")) return;
    try {
      await api.delete(`/api/v1/questions/${id}`);
      showMessage("Question deleted successfully.");
      loadQuestions();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleExcelUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) return;
    setActionLoading(true);
    setUploadResult(null);

    const formData = new FormData();
    formData.append("file", uploadFile);

    try {
      const res = await api.post("/api/v1/questions/bulk-upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data"
        }
      });
      setUploadResult(res.data);
      if (res.data.status === "success") {
        showMessage(`Successfully uploaded ${res.data.added_count} questions.`);
        loadQuestions();
      } else {
        showMessage(`Uploaded ${res.data.added_count} questions, but with some row errors.`, "warning");
        loadQuestions();
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === "object" && (detail.message || detail.errors)) {
        setUploadResult({
          status: "error",
          added_count: 0,
          part_counts: detail.counts || { A: 0, B: 0, C: 0, D: 0 },
          errors: detail.errors || []
        });
        showMessage(detail.message || "Bulk upload validation failed.", "danger");
      } else {
        handleApiError(err);
      }
    } finally {
      setActionLoading(false);
    }
  };

  // ---------------- EXAM SETTINGS MODULE ----------------
  const loadExamSettings = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/v1/exams/active");
      setExamSettings({
        name: res.data.name,
        total_questions: res.data.total_questions,
        duration_minutes: res.data.duration_minutes,
        start_date: res.data.start_date.substring(0, 16),
        end_date: res.data.end_date.substring(0, 16),
        result_visibility: res.data.result_visibility
      });
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.put("/api/v1/exams/settings", examSettings);
      showMessage("Exam settings updated successfully.");
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveCourseSeatCount = async (courseId) => {
    setActionLoading(true);
    try {
      await api.put(`/api/v1/auth/courses/${courseId}`, {
        seat_count: editSeatCount,
        is_active: true
      });
      setEditingCourseId(null);
      showMessage("Course seat count updated successfully.");
      loadCourses();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const loadCommunitySeats = async () => {
    try {
      const res = await api.get("/api/v1/auth/courses/community-seats");
      setCommunitySeats(res.data);
    } catch (err) {
      console.error("Error loading community seats:", err);
    }
  };

  const sumOfEditSeats = () => {
    return Object.values(editCommunitySeats).reduce((a, b) => a + b, 0);
  };

  const handleSaveCourseSeatMatrix = async (courseId) => {
    const sum = sumOfEditSeats();
    if (sum !== editSeatCount) {
      showMessage(`Sum of community seats (${sum}) must equal total course seat capacity (${editSeatCount}).`, "danger");
      return;
    }

    setActionLoading(true);
    try {
      await api.put(`/api/v1/auth/courses/${courseId}`, {
        seat_count: editSeatCount,
        is_active: true
      });

      const payload = Object.entries(editCommunitySeats).map(([code, count]) => ({
        community_code: code,
        seat_count: count
      }));

      await api.put(`/api/v1/auth/courses/${courseId}/community-seats`, payload);

      setEditingCourseId(null);
      showMessage("Course seat capacity and community seat matrix updated successfully.");
      loadCourses();
      loadCommunitySeats();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  // ---------------- COUNSELLING & RANKINGS MODULE ----------------
  const loadLeaderboard = async () => {
    setLoading(true);
    try {
      const params = {
        course_code: leaderboardDegree,
        show_excluded: showExcluded
      };
      if (leaderboardSearch.trim()) params.search = leaderboardSearch;
      if (leaderboardCommunity !== "All") params.community = leaderboardCommunity;

      const res = await api.get("/api/v1/results/course-rankings", { params });
      setLeaderboard(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExportLeaderboard = async () => {
    try {
      const params = {
        course_code: leaderboardDegree,
        show_excluded: showExcluded
      };
      if (leaderboardSearch.trim()) params.search = leaderboardSearch;
      if (leaderboardCommunity !== "All") params.community = leaderboardCommunity;

      const response = await api.get("/api/v1/results/export", {
        params,
        responseType: "blob"
      });

      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      });
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = `Rankings_${leaderboardDegree}_Export.xlsx`;
      link.click();
      showMessage("Rankings Excel sheet downloaded successfully.");
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleConfirmAdmission = async (candidateId, courseId) => {
    setActionLoading(true);
    try {
      await api.post("/api/v1/auth/counselling/confirm", {
        candidate_id: candidateId,
        course_id: courseId
      });
      showMessage("Counselling admission confirmed.");
      loadLeaderboard();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelAdmission = async (candidateId, courseId) => {
    setActionLoading(true);
    try {
      await api.post("/api/v1/auth/counselling/cancel", {
        candidate_id: candidateId,
        course_id: courseId
      });
      showMessage("Counselling admission cancelled.");
      loadLeaderboard();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSearchAttempts = async () => {
    if (!attemptSearchQuery.trim()) {
      showMessage("Please enter a search query.", "danger");
      return;
    }
    setActionLoading(true);
    setAttemptSearchResults(null);
    try {
      const res = await api.get(`/api/v1/auth/attempts/search?query=${encodeURIComponent(attemptSearchQuery)}`);
      setAttemptSearchResults(res.data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReopenAttemptSubmit = async (e) => {
    e.preventDefault();
    if (!reopenModal.reason.trim()) {
      showMessage("Please enter a reason for reopening.", "danger");
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/api/v1/auth/attempts/${reopenModal.attemptId}/reopen`, {
        reason: reopenModal.reason,
        time_extension_minutes: parseInt(reopenModal.timeExtension) || 0
      });
      showMessage(`Attempt successfully reopened for candidate.`);
      setReopenModal({ show: false, attemptId: null, candidateName: "", reason: "", timeExtension: 0 });
      handleSearchAttempts();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleForceSubmitAttemptSubmit = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.post(`/api/v1/auth/attempts/${forceSubmitModal.attemptId}/force-submit`, {
        reason: forceSubmitModal.reason || "Force submitted by admin"
      });
      showMessage(`Attempt force-submitted successfully.`);
      setForceSubmitModal({ show: false, attemptId: null, candidateName: "", reason: "" });
      handleSearchAttempts();
    } catch (err) {
      handleApiError(err);
    } finally {
      setActionLoading(false);
    }
  };

  // Trigger loading when tabs change
  useEffect(() => {
    if (activeTab === "overview") loadOverview();
    else if (activeTab === "students") loadStudentApplications();
    else if (activeTab === "questions") loadQuestions();
    else if (activeTab === "settings") {
      loadExamSettings();
      loadCourses();
      loadCommunitySeats();
    }
    else if (activeTab === "leaderboard") loadLeaderboard();
  }, [activeTab]);

  // Handle leaderboard search and filtering trigger
  useEffect(() => {
    if (activeTab === "leaderboard") {
      const delayDebounce = setTimeout(() => {
        loadLeaderboard();
      }, 300);
      return () => clearTimeout(delayDebounce);
    }
  }, [leaderboardSearch, leaderboardDegree, leaderboardCommunity, showExcluded]);

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    navigate("/admin/login");
  };

  const filteredApps = applications.filter((app) => {
    const term = appSearch.toLowerCase().trim();
    if (!term) return true;
    return (
      app.full_name.toLowerCase().includes(term) ||
      app.application_number.toLowerCase().includes(term) ||
      app.mobile_number.includes(term)
    );
  });

  return (
    <div className="admin-layout animate-fade-in">
      {/* Sidebar Navigation */}
      <div className="admin-sidebar">
        <div style={{ paddingBottom: "1.5rem", borderBottom: "1px solid rgba(255, 255, 255, 0.1)" }}>
          <h2 style={{ fontSize: "1.2rem", fontWeight: "800", color: "#f8fafc" }}>Periyar Entrance</h2>
          <p style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase" }}>Admin Panel</p>
        </div>
        
        <div className="admin-sidebar-menu">
          <div 
            className={`admin-menu-item ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            <LayoutDashboard size={18} />
            Overview
          </div>
          <div 
            className={`admin-menu-item ${activeTab === "students" ? "active" : ""}`}
            onClick={() => setActiveTab("students")}
          >
            <Users size={18} />
            Student Applications
          </div>
          <div 
            className={`admin-menu-item ${activeTab === "questions" ? "active" : ""}`}
            onClick={() => setActiveTab("questions")}
          >
            <BookOpen size={18} />
            Question Bank
          </div>
          <div 
            className={`admin-menu-item ${activeTab === "leaderboard" ? "active" : ""}`}
            onClick={() => setActiveTab("leaderboard")}
          >
            <Trophy size={18} />
            Counselling & Rankings
          </div>
          <div 
            className={`admin-menu-item ${activeTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            <Settings size={18} />
            Config Settings
          </div>
          <div 
            className={`admin-menu-item ${activeTab === "attempts" ? "active" : ""}`}
            onClick={() => setActiveTab("attempts")}
          >
            <Clock size={18} />
            Exam Attempts & Reopen
          </div>
        </div>

        <button 
          className="nav-btn-secondary" 
          onClick={handleLogout}
          style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>

      {/* Main Panel Content */}
      <div className="admin-main">
        {message.text && (
          <div className={`alert alert-${message.type}`} style={{ marginBottom: "1.5rem" }}>
            {message.text}
          </div>
        )}

        {loading ? (
          <div className="spinner" style={{ marginTop: "5rem" }}></div>
        ) : (
          <>
            {/* OVERVIEW TAB */}
            {activeTab === "overview" && stats && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Dashboard Overview</h1>
                </div>

                <div className="stats-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                  <div className="stat-card">
                    <div className="stat-info">
                      <span className="stat-val">{stats.totals.candidates}</span>
                      <span className="stat-lbl">Preloaded Candidates</span>
                    </div>
                    <div className="stat-icon-container icon-blue">
                      <Users size={24} />
                    </div>
                  </div>

                  <div className="stat-card">
                    <div className="stat-info">
                      <span className="stat-val">{stats.totals.applications}</span>
                      <span className="stat-lbl">Course Applications</span>
                    </div>
                    <div className="stat-icon-container icon-gold">
                      <FileSpreadsheet size={24} />
                    </div>
                  </div>

                  <div className="stat-card">
                    <div className="stat-info">
                      <span className="stat-val">{stats.totals.submissions}</span>
                      <span className="stat-lbl">Submitted Exams</span>
                    </div>
                    <div className="stat-icon-container icon-green">
                      <CheckCircle size={24} />
                    </div>
                  </div>

                  <div className="stat-card">
                    <div className="stat-info">
                      <span className="stat-val">{stats.totals.average_score}</span>
                      <span className="stat-lbl">Average Score</span>
                    </div>
                    <div className="stat-icon-container icon-red">
                      <Award size={24} />
                    </div>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", marginTop: "2rem" }}>
                  <div className="dashboard-card">
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1.25rem", color: "var(--primary-dark)" }}>
                      Applications by Program
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {Object.entries(stats.by_degree).map(([degree, count]) => (
                        <div key={degree} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "0.5rem", borderBottom: "1px solid var(--border)" }}>
                          <span style={{ fontWeight: "500" }}>{mapDegreeCode(degree)}</span>
                          <span className="badge badge-blue">{count} applied</span>
                        </div>
                      ))}
                      {Object.keys(stats.by_degree).length === 0 && (
                        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No applications uploaded.</p>
                      )}
                    </div>
                  </div>

                  <div className="dashboard-card">
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1.25rem", color: "var(--primary-dark)" }}>
                      Candidate Community Distribution
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {Object.entries(stats.by_community).map(([comm, count]) => (
                        <div key={comm} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "0.5rem", borderBottom: "1px solid var(--border)" }}>
                          <span style={{ fontWeight: "500" }}>{comm}</span>
                          <span className="badge badge-gold">{count} candidates</span>
                        </div>
                      ))}
                      {Object.keys(stats.by_community).length === 0 && (
                        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No candidates preloaded.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STUDENT APPLICATIONS TAB */}
            {activeTab === "students" && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Student Applications Manager</h1>
                </div>

                <div className="dashboard-card" style={{ marginBottom: "2rem" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)" }}>
                    Import Applications (Excel / CSV)
                  </h3>
                  
                  <form onSubmit={handleExcelApplicationsUpload} style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "220px" }}>
                      <label className="form-label" style={{ fontSize: "0.8rem" }}>Select Target Course</label>
                      <select 
                        className="form-control form-select"
                        value={selectedCourseId}
                        onChange={(e) => setSelectedCourseId(e.target.value)}
                        required
                      >
                        {courses.map(c => (
                          <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                        ))}
                      </select>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", flexGrow: 1 }}>
                      <label className="form-label" style={{ fontSize: "0.8rem" }}>Upload Applications Sheet</label>
                      <input
                        type="file"
                        accept=".xlsx, .xls, .csv"
                        onChange={(e) => setAppUploadFile(e.target.files[0])}
                        className="form-control"
                        required
                      />
                    </div>

                    <button 
                      type="submit" 
                      className="btn btn-primary" 
                      disabled={actionLoading} 
                      style={{ height: "42px", marginTop: "1.3rem", width: "200px", display: "flex", gap: "0.5rem", justifyContent: "center", alignItems: "center" }}
                    >
                      <Upload size={16} /> Import Applications
                    </button>
                  </form>

                  <div style={{ marginTop: "1.25rem", fontSize: "0.85rem", color: "var(--text-muted)", backgroundColor: "#f8fafc", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid #e2e8f0" }}>
                    <strong style={{ color: "var(--primary-dark)", display: "block", marginBottom: "0.4rem" }}>Excel Columns Mapping Reference:</strong>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>
                      <div>
                        <strong style={{ color: "var(--danger)" }}>Required Headers:</strong>
                        <ul style={{ margin: "0.25rem 0 0 1rem", padding: 0 }}>
                          <li>Application No.</li>
                          <li>Student Name</li>
                          <li>Mobile No.</li>
                        </ul>
                      </div>
                      <div>
                        <strong style={{ color: "var(--primary)" }}>Optional Headers:</strong>
                        <ul style={{ margin: "0.25rem 0 0 1rem", padding: 0 }}>
                          <li>DOB (Date of Birth)</li>
                          <li>Community</li>
                          <li>Quota</li>
                          <li>E-mail</li>
                          <li>Percentage (%) (UG)</li>
                          <li>UG Degree</li>
                        </ul>
                      </div>
                      <div>
                        <strong style={{ color: "var(--text-muted)" }}>Ignored / Other:</strong>
                        <ul style={{ margin: "0.25rem 0 0 1rem", padding: 0 }}>
                          <li>S. No</li>
                          <li>Degree/Course</li>
                          <li><em>All unknown headers saved to raw details</em></li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {appUploadResult && (
                    <div style={{ marginTop: "1.5rem", backgroundColor: "#f8fafc", padding: "1.25rem", borderRadius: "var(--radius-md)", border: "1px solid #e2e8f0" }}>
                      <h4 style={{ fontWeight: "700", marginBottom: "0.5rem", color: (appUploadResult.status === "success" || appUploadResult.status === "partial_success") ? "var(--success)" : "var(--danger)" }}>
                        {appUploadResult.status === "error" ? "Import Validation Failed" : `Import Batch ID: ${appUploadResult.batch_id} (${appUploadResult.status.toUpperCase()})`}
                      </h4>
                      
                      {appUploadResult.status !== "error" && (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "1rem", fontSize: "0.9rem", marginBottom: "1rem" }}>
                          <div><strong>Total Rows:</strong> {appUploadResult.total_rows}</div>
                          <div style={{ color: "var(--success)" }}><strong>Inserted:</strong> {appUploadResult.inserted_count}</div>
                          <div style={{ color: "var(--primary)" }}><strong>Updated:</strong> {appUploadResult.updated_count}</div>
                          <div style={{ color: "var(--text-muted)" }}><strong>Skipped:</strong> {appUploadResult.skipped_count}</div>
                          <div style={{ color: "var(--danger)" }}><strong>Errors:</strong> {appUploadResult.error_count}</div>
                          {appUploadResult.blank_rows_skipped !== undefined && appUploadResult.blank_rows_skipped > 0 && (
                            <div style={{ color: "var(--text-muted)" }}><strong>Blank Skipped:</strong> {appUploadResult.blank_rows_skipped}</div>
                          )}
                        </div>
                      )}

                      {appUploadResult.detected_columns && (
                        <div style={{ fontSize: "0.85rem", color: "var(--text-main)", backgroundColor: "#fff", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid #e2e8f0", marginTop: "0.5rem" }}>
                          <div style={{ marginBottom: "0.25rem" }}>
                            <strong>Detected Columns:</strong> {appUploadResult.detected_columns.join(", ") || "None"}
                          </div>
                          {appUploadResult.missing_required_columns && appUploadResult.missing_required_columns.length > 0 && (
                            <div style={{ color: "var(--danger)", marginBottom: "0.25rem" }}>
                              <strong>Missing Required Columns:</strong> {appUploadResult.missing_required_columns.join(", ")}
                            </div>
                          )}
                          {appUploadResult.ignored_columns && appUploadResult.ignored_columns.length > 0 && (
                            <div style={{ color: "var(--text-muted)", marginBottom: "0.25rem" }}>
                              <strong>Ignored Columns:</strong> {appUploadResult.ignored_columns.join(", ")}
                            </div>
                          )}
                          {appUploadResult.blank_rows_skipped !== undefined && appUploadResult.blank_rows_skipped > 0 && (
                            <div style={{ color: "var(--text-muted)" }}>
                              <strong>Blank Rows Skipped:</strong> {appUploadResult.blank_rows_skipped}
                            </div>
                          )}
                        </div>
                      )}

                      {appUploadResult.warnings && appUploadResult.warnings.length > 0 && (
                        <div style={{ marginTop: "1rem", backgroundColor: "#fffbeb", border: "1px solid #fde68a", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                          <p style={{ fontWeight: "700", color: "#b45309", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Duplicate Mobile Warnings / Reset Triggers / Mismatches:</p>
                          <div style={{ maxHeight: "120px", overflowY: "auto", fontSize: "0.8rem", color: "#78350f" }}>
                            {appUploadResult.warnings.map((w, idx) => (
                              <div key={idx} style={{ marginBottom: "0.25rem" }}>⚠️ {w}</div>
                            ))}
                          </div>
                        </div>
                      )}

                      {appUploadResult.errors && appUploadResult.errors.length > 0 && (
                        <div style={{ marginTop: "1rem", backgroundColor: "#fef2f2", border: "1px solid #fecaca", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                          <p style={{ fontWeight: "700", color: "#b91c1c", fontSize: "0.85rem", marginBottom: "0.25rem" }}>Row Error Details:</p>
                          <div style={{ maxHeight: "120px", overflowY: "auto", fontSize: "0.8rem", color: "#991b1b" }}>
                            {appUploadResult.errors.map((e, idx) => (
                              <div key={idx} style={{ marginBottom: "0.25rem" }}>❌ {e}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="filters-bar">
                  <div className="search-input-container" style={{ maxWidth: "450px" }}>
                    <Search size={16} className="search-icon" />
                    <input
                      type="text"
                      className="form-control search-input"
                      placeholder="Search applications by Name, Mobile, App No..."
                      value={appSearch}
                      onChange={(e) => setAppSearch(e.target.value)}
                    />
                  </div>
                </div>

                {(() => {
                  const term = appSearch.trim().toLowerCase();
                  if (!term) return null;
                  
                  // Keep digits only to check if searching for a mobile number
                  const searchDigits = term.replace(/\D/g, "");
                  if (!searchDigits) return null;
                  
                  // Find all applications where mobile matches
                  const matchedAppsByMobile = applications.filter((app) => {
                    const appMobileClean = app.mobile_number.replace(/\D/g, "");
                    return appMobileClean.includes(searchDigits);
                  });

                  if (matchedAppsByMobile.length === 0) return null;

                  // Group matches by candidate_id
                  const candidateGroups = {};
                  matchedAppsByMobile.forEach((app) => {
                    if (!candidateGroups[app.candidate_id]) {
                      candidateGroups[app.candidate_id] = {
                        candidateId: app.candidate_id,
                        candidateMobile: app.mobile_number,
                        applications: []
                      };
                    }
                    candidateGroups[app.candidate_id].applications.push(app);
                  });

                  // For each candidate group, find ALL applications in the system with that candidate_id
                  const candidateIds = Object.keys(candidateGroups);
                  const debugCards = candidateIds.map((cidStr) => {
                    const cid = parseInt(cidStr, 10);
                    const allAppsForCand = applications.filter(app => app.candidate_id === cid);
                    const appNumbers = allAppsForCand.map(app => app.application_number);
                    const courseCodes = allAppsForCand.map(app => app.course_code || (app.course_id === 1 ? "MCA" : app.course_id === 2 ? "MSC_CS" : app.course_id === 3 ? "MSC_DS" : `ID: ${app.course_id}`));
                    const group = candidateGroups[cidStr];

                    return (
                      <div 
                        key={cid}
                        className="dashboard-card animate-slide-up" 
                        style={{ 
                          borderLeft: "4px solid var(--primary)", 
                          backgroundColor: "#f8fafc", 
                          marginBottom: "1.5rem",
                          padding: "1rem" 
                        }}
                      >
                        <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--primary-dark)", fontSize: "0.95rem", fontWeight: "700" }}>
                          Candidate Linking Info (Debug View)
                        </h4>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", fontSize: "0.85rem" }}>
                          <div>
                            <strong>Candidate ID:</strong> <span style={{ fontFamily: "monospace", color: "var(--primary)", fontWeight: "600" }}>{cid}</span>
                          </div>
                          <div>
                            <strong>Candidate Mobile:</strong> <span>{group.candidateMobile}</span>
                          </div>
                          <div>
                            <strong>Linked Applications ({appNumbers.length}):</strong>
                            <div style={{ marginTop: "0.25rem" }}>
                              {appNumbers.map(an => (
                                <span key={an} className="badge badge-blue" style={{ marginRight: "0.25rem", marginBottom: "0.25rem" }}>{an}</span>
                              ))}
                            </div>
                          </div>
                          <div>
                            <strong>Linked Course Codes:</strong>
                            <div style={{ marginTop: "0.25rem" }}>
                              {courseCodes.map((cc, idx) => (
                                <span key={idx} className="badge badge-gold" style={{ marginRight: "0.25rem", marginBottom: "0.25rem" }}>{cc}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  });

                  return (
                    <div style={{ marginBottom: "1.5rem" }}>
                      {debugCards}
                    </div>
                  );
                })()}

                <div className="admin-table-card">
                  <div className="admin-table-scroll applications-table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Application No</th>
                          <th>Student Name</th>
                          <th>Course</th>
                          <th>Mobile</th>
                          <th>Community</th>
                          <th>Email</th>
                          <th style={{ textAlign: "right" }}>UG %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredApps.map((app) => (
                          <tr key={app.id}>
                            <td style={{ fontWeight: "700", color: "var(--primary)" }}>{app.application_number}</td>
                            <td style={{ fontWeight: "600" }}>{app.full_name}</td>
                            <td>
                              <span className="badge badge-blue">
                                {app.course_code || (app.course_id === 1 ? "MCA" : app.course_id === 2 ? "MSC_CS" : app.course_id === 3 ? "MSC_DS" : `ID: ${app.course_id}`)}
                              </span>
                            </td>
                            <td>{app.mobile_number}</td>
                            <td>{app.community || "OC"}</td>
                            <td>{app.email || "-"}</td>
                            <td style={{ textAlign: "right", fontWeight: "600" }}>
                              {app.ug_marks !== null ? `${app.ug_marks}%` : "N/A"}
                            </td>
                          </tr>
                        ))}
                        {filteredApps.length === 0 && (
                          <tr>
                            <td colSpan="7" style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem" }}>
                              No applications matching filter search criteria.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* QUESTION BANK TAB */}
            {activeTab === "questions" && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Question Management ({questions.length})</h1>
                  <button className="btn btn-primary" onClick={handleOpenAddQuestion} style={{ width: "auto" }}>
                    <Plus size={18} /> Add Question
                  </button>
                </div>

                <div className="dashboard-card" style={{ marginBottom: "2rem" }}>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)" }}>
                    Bulk Upload Questions (Excel / CSV)
                  </h3>
                  <form onSubmit={handleExcelUpload} style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                    <input
                      type="file"
                      accept=".xlsx, .xls, .csv"
                      onChange={(e) => setUploadFile(e.target.files[0])}
                      className="form-control"
                      style={{ flexGrow: "1" }}
                      required
                    />
                    <button type="submit" className="btn btn-secondary" disabled={actionLoading} style={{ width: "180px", display: "flex", gap: "0.5rem" }}>
                      <Upload size={16} /> Upload Questions
                    </button>
                  </form>
                  {uploadResult && (
                    <div style={{ marginTop: "1rem", backgroundColor: "#f8fafc", padding: "1.25rem", borderRadius: "var(--radius-md)", border: "1px solid #e2e8f0" }}>
                      <p style={{ fontWeight: "700", color: uploadResult.status === "success" ? "var(--success)" : "var(--danger)", fontSize: "1.05rem", marginBottom: "0.75rem" }}>
                        {uploadResult.status === "error" ? "Upload Failed!" : `Upload Complete! Successfully added ${uploadResult.added_count} questions.`}
                      </p>
                      
                      {uploadResult.part_counts && (
                        <div style={{ backgroundColor: "#fff", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem", marginBottom: "1rem" }}>
                          <h4 style={{ margin: "0 0 0.75rem 0", color: "var(--primary-dark)", fontSize: "0.9rem", fontWeight: "700" }}>Upload Summary:</h4>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                              <span>Part A - Quantitative Ability:</span>
                              <strong style={{ color: (uploadResult.part_counts.A || 0) === 25 ? "var(--success)" : "var(--danger)" }}>
                                {uploadResult.part_counts.A || 0} / 25
                              </strong>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                              <span>Part B - Analytical Reasoning:</span>
                              <strong style={{ color: (uploadResult.part_counts.B || 0) === 25 ? "var(--success)" : "var(--danger)" }}>
                                {uploadResult.part_counts.B || 0} / 25
                              </strong>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                              <span>Part C - Logical Reasoning:</span>
                              <strong style={{ color: (uploadResult.part_counts.C || 0) === 25 ? "var(--success)" : "var(--danger)" }}>
                                {uploadResult.part_counts.C || 0} / 25
                              </strong>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                              <span>Part D - Computer Awareness:</span>
                              <strong style={{ color: (uploadResult.part_counts.D || 0) === 25 ? "var(--success)" : "var(--danger)" }}>
                                {uploadResult.part_counts.D || 0} / 25
                              </strong>
                            </div>
                            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.5rem", display: "flex", justifyContent: "space-between", fontWeight: "700" }}>
                              <span>Total:</span>
                              <span>{uploadResult.added_count || 0} / 100</span>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {uploadResult.errors && uploadResult.errors.length > 0 && (
                        <div style={{ marginTop: "0.5rem", maxHeight: "150px", overflowY: "auto" }}>
                          <p style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--danger)" }}>Row Errors:</p>
                          <ul style={{ paddingLeft: "1.25rem", fontSize: "0.8rem", color: "var(--danger)" }}>
                            {uploadResult.errors.map((err, idx) => (
                              <li key={idx}>{err}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="filters-bar" style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1.5rem" }}>
                  <span style={{ fontWeight: "700", fontSize: "0.9rem" }}>Filter by Part:</span>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    {["All", "A", "B", "C", "D"].map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setQuestionPartFilter(p)}
                        className={`btn ${questionPartFilter === p ? "btn-primary" : "btn-secondary"}`}
                        style={{ padding: "0.35rem 1rem", fontSize: "0.85rem", width: "auto" }}
                      >
                        {p === "All" ? "All Sections" : `Part ${p}`}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="admin-table-card">
                  <div className="admin-table-scroll questions-table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: "80px" }}>Part</th>
                          <th style={{ width: "80px" }}>S. No</th>
                          <th style={{ width: "35%" }}>Question</th>
                          <th>Options (A, B, C, D)</th>
                          <th>Correct</th>
                          <th style={{ textAlign: "right" }}>Mark</th>
                          <th style={{ width: "100px", textAlign: "center" }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {questions
                          .filter((q) => questionPartFilter === "All" || q.part_code === questionPartFilter)
                          .map((q) => (
                            <tr key={q.id}>
                              <td style={{ fontWeight: "700", color: "var(--primary)" }}>{q.part_code ? `Part ${q.part_code}` : "-"}</td>
                              <td style={{ fontWeight: "600" }}>{q.source_s_no !== null && q.source_s_no !== undefined ? q.source_s_no : "-"}</td>
                              <td style={{ fontWeight: "500", verticalAlign: "top" }}>
                                <div>{q.question_text}</div>
                                {q.image_url && (
                                  <div style={{ marginTop: "0.5rem" }}>
                                    <img 
                                      src={q.image_url} 
                                      alt="Question diagram" 
                                      style={{ maxWidth: "150px", maxHeight: "80px", borderRadius: "4px", border: "1px solid var(--border)" }} 
                                    />
                                  </div>
                                )}
                              </td>
                              <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)", verticalAlign: "top" }}>
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                                  {[
                                    { label: "A", val: q.option_a, img: q.option_a_image_url },
                                    { label: "B", val: q.option_b, img: q.option_b_image_url },
                                    { label: "C", val: q.option_c, img: q.option_c_image_url },
                                    { label: "D", val: q.option_d, img: q.option_d_image_url },
                                  ].map((opt) => (
                                    <div key={opt.label} style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                                      <span style={{ fontWeight: "600" }}>{opt.label}:</span>
                                      {opt.val && <span>{opt.val}</span>}
                                      {opt.img && (
                                        <img 
                                          src={opt.img} 
                                          alt={`Opt ${opt.label}`} 
                                          style={{ height: "28px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }} 
                                        />
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </td>
                              <td><span className="badge badge-blue">{q.correct_option}</span></td>
                              <td style={{ textAlign: "right", fontWeight: "600" }}>{q.marks}</td>
                              <td style={{ textAlign: "center" }}>
                                <div style={{ display: "flex", gap: "0.25rem", justifyContent: "center" }}>
                                  <button className="action-btn edit" onClick={() => handleOpenEditQuestion(q)}>
                                    <Edit size={16} />
                                  </button>
                                  <button className="action-btn delete" onClick={() => handleDeleteQuestion(q.id)}>
                                    <Trash2 size={16} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        {questions.filter((q) => questionPartFilter === "All" || q.part_code === questionPartFilter).length === 0 && (
                          <tr>
                            <td colSpan="7" style={{ textAlign: "center", color: "var(--text-muted)" }}>
                              No questions uploaded yet. Start adding manually or upload Excel sheet.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* COUNSELLING & RANKINGS TAB */}
            {activeTab === "leaderboard" && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Counselling & Course-wise Rankings</h1>
                  <button className="btn btn-primary" onClick={handleExportLeaderboard} style={{ width: "auto", display: "flex", gap: "0.5rem" }}>
                    <FileDown size={18} /> Export Course Rank List
                  </button>
                </div>

                {/* Info summary header for selected course */}
                {courses.find(c => c.code === leaderboardDegree) && (
                  <div style={{ 
                    backgroundColor: "#eff6ff", 
                    border: "1px solid #bfdbfe", 
                    padding: "1.25rem", 
                    borderRadius: "var(--radius-md)", 
                    marginBottom: "1.5rem",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "1.5rem",
                    fontSize: "0.95rem"
                  }}>
                    <div>
                      <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Selected Course</span>
                      <p style={{ fontWeight: "700", color: "var(--primary-dark)", fontSize: "1.1rem" }}>
                        {courses.find(c => c.code === leaderboardDegree).name}
                      </p>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Seat Capacity</span>
                      <p style={{ fontWeight: "700", color: "var(--primary-dark)", fontSize: "1.1rem" }}>
                        {courses.find(c => c.code === leaderboardDegree).seat_count} Seats
                      </p>
                    </div>
                    <div>
                      <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Total Confirmed</span>
                      <p style={{ fontWeight: "700", color: "var(--success)", fontSize: "1.1rem" }}>
                        {leaderboard.filter(l => l.confirmation_status === "Confirmed").length} Candidates
                      </p>
                    </div>
                  </div>
                )}

                {/* Filter and Search Bar */}
                <div className="filters-bar" style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr 0.8fr 1fr", gap: "1rem", alignItems: "center" }}>
                  <div className="search-input-container">
                    <Search size={16} className="search-icon" />
                    <input
                      type="text"
                      className="form-control search-input"
                      placeholder="Search by Student Name or App No..."
                      value={leaderboardSearch}
                      onChange={(e) => setLeaderboardSearch(e.target.value)}
                    />
                  </div>

                  <select
                    className="form-control filter-select"
                    value={leaderboardDegree}
                    onChange={(e) => setLeaderboardDegree(e.target.value)}
                  >
                    <option value="MCA">MCA</option>
                    <option value="MSC_CS">M.Sc Computer Science</option>
                    <option value="MSC_DS">M.Sc Data Science</option>
                  </select>

                  <select
                    className="form-control filter-select"
                    value={leaderboardCommunity}
                    onChange={(e) => setLeaderboardCommunity(e.target.value)}
                  >
                    <option value="All">All Communities</option>
                    <option value="OC">OC / Open Competition</option>
                    <option value="BC">BC</option>
                    <option value="BCM">BC(M)</option>
                    <option value="MBC">MBC&DNC</option>
                    <option value="SC">SC</option>
                    <option value="SCA">SC(A)</option>
                    <option value="ST">ST</option>
                  </select>

                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", userSelect: "none", fontSize: "0.9rem", fontWeight: "600" }}>
                    <input 
                      type="checkbox" 
                      checked={showExcluded}
                      onChange={(e) => setShowExcluded(e.target.checked)}
                      style={{ width: "16px", height: "16px" }}
                    />
                    Include Excluded (Admitted Elsewhere)
                  </label>
                </div>

                <div className="admin-table-card">
                  <div className="admin-table-scroll counselling-table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: "70px" }}>Orig Rank</th>
                          <th style={{ width: "70px" }}>Active Rank</th>
                          <th style={{ width: "70px" }}>Comm Rank</th>
                          <th>Application No</th>
                          <th>Student Name</th>
                          <th>Community (Raw)</th>
                          <th>Community (Norm)</th>
                          <th style={{ textAlign: "right" }}>Quota Seats</th>
                          <th>Selection Bucket</th>
                          <th style={{ textAlign: "right" }}>Entrance Score</th>
                          <th style={{ textAlign: "right" }}>UG %</th>
                          <th style={{ textAlign: "right" }}>Entrance 50%</th>
                          <th style={{ textAlign: "right" }}>UG 50%</th>
                          <th style={{ textAlign: "right" }}>Final Score</th>
                          <th>Counselling Status</th>
                          <th style={{ textAlign: "center", width: "180px" }}>Admission Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboard.map((r) => {
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
                          } else if (r.confirmation_status === "Incomplete UG Percentage") {
                            badgeColor = "#c2410c";
                            badgeBg = "#ffedd5";
                          }

                          return (
                            <tr key={r.application_number} style={{ opacity: r.confirmation_status === "Excluded" ? 0.65 : 1 }}>
                              <td style={{ textAlign: "center", fontWeight: "600" }}>{r.original_rank}</td>
                              <td style={{ textAlign: "center", fontWeight: "700", color: "var(--primary-dark)" }}>
                                {r.active_rank === -1 ? "-" : r.active_rank}
                              </td>
                              <td style={{ textAlign: "center", fontWeight: "600" }}>
                                {r.community_rank === -1 ? "-" : r.community_rank}
                              </td>
                              <td style={{ fontWeight: "700", color: "var(--primary)" }}>{r.application_number}</td>
                              <td style={{ fontWeight: "600" }}>
                                {r.student_name}
                                {r.excluded_reason && (
                                  <div style={{ fontSize: "0.75rem", color: "#b91c1c", fontWeight: "500", marginTop: "0.15rem" }}>
                                    ({r.excluded_reason})
                                  </div>
                                )}
                              </td>
                              <td>{r.community}</td>
                              <td style={{ fontWeight: "600" }}>{r.normalized_community}</td>
                              <td style={{ textAlign: "right", fontWeight: "600" }}>{r.community_seat_count}</td>
                              <td style={{ fontWeight: "700", color: "var(--primary-dark)" }}>{r.final_selection_bucket_name || "-"}</td>
                              <td style={{ textAlign: "right", fontWeight: "700" }}>{r.score}</td>
                              <td style={{ textAlign: "right" }}>
                                {r.ug_percentage !== null && r.ug_percentage !== undefined ? `${r.ug_percentage}%` : "Incomplete"}
                              </td>
                              <td style={{ textAlign: "right" }}>
                                {r.entrance_weighted_score !== null && r.entrance_weighted_score !== undefined ? r.entrance_weighted_score : "-"}
                              </td>
                              <td style={{ textAlign: "right" }}>
                                {r.ug_weighted_score !== null && r.ug_weighted_score !== undefined ? r.ug_weighted_score : "-"}
                              </td>
                              <td style={{ textAlign: "right", fontWeight: "800", color: "var(--primary-dark)" }}>
                                {r.final_score !== null && r.final_score !== undefined ? r.final_score : "Incomplete"}
                              </td>
                              <td>
                                <span style={{ 
                                  fontSize: "0.8rem", 
                                  fontWeight: "700", 
                                  color: badgeColor, 
                                  backgroundColor: badgeBg, 
                                  padding: "0.25rem 0.6rem", 
                                  borderRadius: "12px" 
                                }}>
                                  {r.confirmation_status}
                                </span>
                              </td>
                              <td style={{ textAlign: "center" }}>
                                {r.confirmation_status === "Confirmed" ? (
                                  <button 
                                    className="btn btn-secondary" 
                                    onClick={() => handleCancelAdmission(r.candidate_id, courses.find(c => c.code === leaderboardDegree)?.id)}
                                    disabled={actionLoading}
                                    style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem", backgroundColor: "#ef4444", color: "#fff", borderColor: "#ef4444" }}
                                  >
                                    Cancel Admission
                                  </button>
                                ) : (
                                  <button 
                                    className="btn btn-primary"
                                    onClick={() => handleConfirmAdmission(r.candidate_id, courses.find(c => c.code === leaderboardDegree)?.id)}
                                    disabled={actionLoading || r.confirmation_status === "Excluded" || r.confirmation_status === "Incomplete UG Percentage"}
                                    style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}
                                  >
                                    Confirm Admission
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                        {leaderboard.length === 0 && (
                          <tr>
                            <td colSpan="16" style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem" }}>
                              No rankings or counselling profiles found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* EXAM & SEAT SETTINGS TAB */}
            {activeTab === "settings" && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Portal Configurations</h1>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", alignItems: "start" }}>
                  <div className="glass-card">
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1.2rem", color: "var(--primary-dark)" }}>
                      Entrance Exam Parameters
                    </h3>
                    <form onSubmit={handleSaveSettings}>
                      <div className="form-group" style={{ marginBottom: "1rem" }}>
                        <label className="form-label">Exam Name</label>
                        <input
                          className="form-control"
                          type="text"
                          value={examSettings.name}
                          onChange={(e) => setExamSettings({ ...examSettings, name: e.target.value })}
                          required
                        />
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                        <div className="form-group">
                          <label className="form-label">Total Questions</label>
                          <input
                            className="form-control"
                            type="number"
                            value={examSettings.total_questions}
                            onChange={(e) => setExamSettings({ ...examSettings, total_questions: parseInt(e.target.value, 10) })}
                            required
                          />
                        </div>

                        <div className="form-group">
                          <label className="form-label">Duration (Minutes)</label>
                          <input
                            className="form-control"
                            type="number"
                            value={examSettings.duration_minutes}
                            onChange={(e) => setExamSettings({ ...examSettings, duration_minutes: parseInt(e.target.value, 10) })}
                            required
                          />
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                        <div className="form-group">
                          <label className="form-label">Start Date & Time (UTC)</label>
                          <input
                            className="form-control"
                            type="datetime-local"
                            value={examSettings.start_date}
                            onChange={(e) => setExamSettings({ ...examSettings, start_date: e.target.value })}
                            required
                          />
                        </div>

                        <div className="form-group">
                          <label className="form-label">End Date & Time (UTC)</label>
                          <input
                            className="form-control"
                            type="datetime-local"
                            value={examSettings.end_date}
                            onChange={(e) => setExamSettings({ ...examSettings, end_date: e.target.value })}
                            required
                          />
                        </div>
                      </div>

                      <div className="form-group" style={{ display: "flex", alignItems: "center", gap: "0.5rem", margin: "1.5rem 0" }}>
                        <input
                          type="checkbox"
                          id="result-visibility"
                          checked={examSettings.result_visibility}
                          onChange={(e) => setExamSettings({ ...examSettings, result_visibility: e.target.checked })}
                          style={{ width: "18px", height: "18px", cursor: "pointer" }}
                        />
                        <label htmlFor="result-visibility" style={{ fontSize: "0.95rem", fontWeight: "600", cursor: "pointer" }}>
                          Show detailed score & key breakdown to students upon submission
                        </label>
                      </div>

                      <button
                        className="btn btn-primary"
                        type="submit"
                        disabled={actionLoading}
                        style={{ width: "100%" }}
                      >
                        {actionLoading ? "Updating..." : "Save Exam Config"}
                      </button>
                    </form>
                  </div>

                  <div className="glass-card">
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1.2rem", color: "var(--primary-dark)" }}>
                      Course Settings & Seat Capacities
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                      {courses.map((c) => (
                        <div 
                          key={c.id} 
                          style={{ 
                            backgroundColor: "#f8fafc", 
                            padding: "1rem", 
                            borderRadius: "var(--radius-md)", 
                            border: "1px solid #e2e8f0" 
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>
                              <span style={{ fontWeight: "700", color: "var(--primary)" }}>{c.code}</span>
                              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>{c.name}</p>
                              {editingCourseId !== c.id && (
                                <div style={{ marginTop: "0.5rem", display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                                  {communitySeats.filter(s => s.course_id === c.id).map(seat => (
                                    <span key={seat.id} style={{ fontSize: "0.75rem", backgroundColor: "#fff", padding: "0.15rem 0.4rem", borderRadius: "4px", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                                      <strong>{seat.community_code}:</strong> {seat.seat_count}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                            
                            {editingCourseId !== c.id && (
                              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                                <span style={{ fontWeight: "700", fontSize: "1rem" }}>{c.seat_count} Seats</span>
                                <button 
                                  className="action-btn edit" 
                                  onClick={() => {
                                    setEditingCourseId(c.id);
                                    setEditSeatCount(c.seat_count);
                                    const courseSeatsObj = {};
                                    communitySeats.filter(s => s.course_id === c.id).forEach(s => {
                                      courseSeatsObj[s.community_code] = s.seat_count;
                                    });
                                    setEditCommunitySeats(courseSeatsObj);
                                  }}
                                >
                                  <Edit size={16} />
                                </button>
                              </div>
                            )}
                          </div>

                          {editingCourseId === c.id && (
                            <div style={{ marginTop: "1rem", borderTop: "1px dashed var(--border)", paddingTop: "0.75rem" }}>
                              <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "0.75rem" }}>
                                <label style={{ fontSize: "0.85rem", fontWeight: "700" }}>Total Capacity:</label>
                                <input 
                                  type="number" 
                                  className="form-control"
                                  style={{ width: "80px", padding: "0.35rem" }}
                                  value={editSeatCount}
                                  onChange={(e) => setEditSeatCount(parseInt(e.target.value, 10) || 0)}
                                />
                              </div>

                              <label style={{ fontSize: "0.85rem", fontWeight: "700", display: "block", marginBottom: "0.5rem" }}>Community-wise Seat Distribution:</label>
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.75rem", marginBottom: "1rem" }}>
                                {communitySeats.filter(s => s.course_id === c.id).map(seat => (
                                  <div key={seat.id} style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                                    <span style={{ fontSize: "0.75rem", fontWeight: "600", color: "var(--text-secondary)" }}>{seat.community_name} ({seat.community_code}):</span>
                                    <input 
                                      type="number"
                                      className="form-control"
                                      style={{ padding: "0.25rem", width: "100%" }}
                                      value={editCommunitySeats[seat.community_code] !== undefined ? editCommunitySeats[seat.community_code] : seat.seat_count}
                                      onChange={(e) => {
                                        const val = parseInt(e.target.value, 10) || 0;
                                        setEditCommunitySeats(prev => ({
                                          ...prev,
                                          [seat.community_code]: val
                                        }));
                                      }}
                                    />
                                  </div>
                                ))}
                              </div>

                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
                                <div style={{ fontSize: "0.85rem", fontWeight: "700", color: (sumOfEditSeats() === editSeatCount ? "var(--success)" : "var(--danger)") }}>
                                  Sum of Community Seats: {sumOfEditSeats()} / {editSeatCount}
                                </div>
                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                  <button 
                                    className="btn btn-secondary" 
                                    style={{ padding: "0.35rem 0.75rem", fontSize: "0.85rem", width: "auto" }}
                                    onClick={() => setEditingCourseId(null)}
                                  >
                                    Cancel
                                  </button>
                                  <button 
                                    className="btn btn-primary" 
                                    style={{ padding: "0.35rem 0.75rem", fontSize: "0.85rem", width: "auto" }}
                                    onClick={() => handleSaveCourseSeatMatrix(c.id)}
                                    disabled={actionLoading}
                                  >
                                    {actionLoading ? "Saving..." : "Save Matrix"}
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* EXAM ATTEMPTS & REOPEN TAB */}
            {activeTab === "attempts" && (
              <div>
                <div className="admin-header">
                  <h1 className="admin-title">Exam Attempts & Reopen Management</h1>
                </div>

                <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1rem", color: "var(--primary-dark)" }}>
                    Search Candidate Attempt
                  </h3>
                  <div style={{ display: "flex", gap: "1rem" }}>
                    <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="Enter Application Number or Mobile Number..."
                        value={attemptSearchQuery}
                        onChange={(e) => setAttemptSearchQuery(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") handleSearchAttempts(); }}
                      />
                    </div>
                    <button 
                      className="btn btn-primary" 
                      onClick={handleSearchAttempts}
                      disabled={actionLoading}
                      style={{ width: "150px" }}
                    >
                      {actionLoading ? "Searching..." : "Search"}
                    </button>
                  </div>
                </div>

                {/* Search Results */}
                {attemptSearchResults && (
                  <div className="glass-card">
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "1.2rem", color: "var(--primary-dark)" }}>
                      Search Results ({attemptSearchResults.length})
                    </h3>
                    {attemptSearchResults.length === 0 ? (
                      <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>
                        No exam attempts or candidates found matching the query.
                      </p>
                    ) : (
                      <div className="admin-table-card">
                        <div className="admin-table-scroll">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Student Details</th>
                                <th>Course Applications</th>
                                <th>Attempt Status</th>
                                <th style={{ textAlign: "center" }}>Progress</th>
                                <th style={{ textAlign: "center" }}>Violations</th>
                                <th>Last Active / Submitted</th>
                                <th>Submission Info</th>
                                <th style={{ textAlign: "center" }}>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {attemptSearchResults.map((res) => {
                                let badgeColor = "var(--text-muted)";
                                let badgeBg = "#f1f5f9";
                                const status = res.status;
                                if (status === "active" || status === "admin_reopened") {
                                  badgeColor = "#1e3a8a";
                                  badgeBg = "#dbeafe";
                                } else if (status === "submitted") {
                                  badgeColor = "#166534";
                                  badgeBg = "#dcfce7";
                                } else if (status === "auto_submitted") {
                                  badgeColor = "#991b1b";
                                  badgeBg = "#fee2e2";
                                } else if (status === "force_submitted") {
                                  badgeColor = "#854d0e";
                                  badgeBg = "#fef9c3";
                                }

                                return (
                                  <tr key={res.candidate.id}>
                                    <td>
                                      <div style={{ fontWeight: "700" }}>{res.candidate.full_name}</div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Mob: {res.candidate.mobile_number}</div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Email: {res.candidate.email || "-"}</div>
                                    </td>
                                    <td>
                                      {res.applications.map(app => (
                                        <div key={app.application_number} style={{ fontSize: "0.85rem", marginBottom: "0.2rem" }}>
                                          <span style={{ fontWeight: "700" }}>{app.course_code}</span>: {app.application_number} ({app.ug_marks ? `${app.ug_marks}%` : "Incomplete UG"})
                                        </div>
                                      ))}
                                    </td>
                                    <td>
                                      <span style={{ 
                                        fontSize: "0.8rem", 
                                        fontWeight: "700", 
                                        color: badgeColor, 
                                        backgroundColor: badgeBg, 
                                        padding: "0.25rem 0.6rem", 
                                        borderRadius: "12px" 
                                      }}>
                                        {status}
                                      </span>
                                    </td>
                                    <td style={{ textAlign: "center" }}>
                                      {res.attempt_id ? (
                                        <div>
                                          <div style={{ fontWeight: "700" }}>{res.answered_count} / 100</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Score: {res.score !== null ? res.score : "-"}</div>
                                        </div>
                                      ) : "-"}
                                    </td>
                                    <td style={{ textAlign: "center", fontWeight: "700", color: res.violation_count > 0 ? "var(--danger)" : "var(--text)" }}>
                                      {res.attempt_id ? res.violation_count : "-"}
                                    </td>
                                    <td>
                                      {res.attempt_id ? (
                                        <div style={{ fontSize: "0.85rem" }}>
                                          <div>Active: {res.last_activity_at ? new Date(res.last_activity_at).toLocaleString() : "-"}</div>
                                          <div>Submit: {res.submitted_at ? new Date(res.submitted_at).toLocaleString() : "-"}</div>
                                        </div>
                                      ) : "-"}
                                    </td>
                                    <td>
                                      {res.attempt_id && (res.submit_source || res.submitted_reason) ? (
                                        <div style={{ fontSize: "0.8rem", maxWidth: "200px", wordBreak: "break-word" }}>
                                          <div>Source: <span style={{ fontWeight: "700" }}>{res.submit_source || "-"}</span></div>
                                          <div>Reason: {res.submitted_reason || "-"}</div>
                                          {res.reopen_count > 0 && <div style={{ color: "var(--primary)", fontWeight: "600" }}>Reopened: {res.reopen_count} time(s)</div>}
                                        </div>
                                      ) : "-"}
                                    </td>
                                    <td style={{ textAlign: "center" }}>
                                      {res.attempt_id && (status === "submitted" || status === "auto_submitted" || status === "force_submitted") && (
                                        <button 
                                          className="btn btn-primary"
                                          onClick={() => setReopenModal({ 
                                            show: true, 
                                            attemptId: res.attempt_id, 
                                            candidateName: res.candidate.full_name, 
                                            reason: "", 
                                            timeExtension: 0 
                                          })}
                                          style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem", width: "auto" }}
                                        >
                                          Reopen Attempt
                                        </button>
                                      )}
                                      {res.attempt_id && (status === "active" || status === "admin_reopened") && (
                                        <button 
                                          className="btn btn-secondary"
                                          onClick={() => setForceSubmitModal({ 
                                            show: true, 
                                            attemptId: res.attempt_id, 
                                            candidateName: res.candidate.full_name, 
                                            reason: "" 
                                          })}
                                          style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem", width: "auto", backgroundColor: "#ef4444", color: "#fff", borderColor: "#ef4444" }}
                                        >
                                          Force Submit
                                        </button>
                                      )}
                                      {!res.attempt_id && "-"}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Question Add/Edit Modal */}
      {questionModal.show && (
        <div className="modal-backdrop">
          <div className="modal-content animate-slide-up" style={{ maxWidth: "600px" }}>
            <div className="modal-header">
              <h2 className="modal-title">
                {questionModal.editId ? `Edit Question #${questionModal.editId}` : "Create New Question"}
              </h2>
            </div>
            <form onSubmit={handleSaveQuestion}>
              <div className="modal-body">
                <div className="form-group" style={{ marginBottom: "1rem" }}>
                  <label className="form-label">Question Text</label>
                  <textarea
                    className="form-control"
                    rows="3"
                    value={questionForm.question_text}
                    onChange={(e) => setQuestionForm({ ...questionForm, question_text: e.target.value })}
                    required
                  />
                  <label style={{ fontSize: "0.85rem", fontWeight: "500", color: "var(--text-muted)", marginTop: "0.25rem", display: "block" }}>Question Image (Optional)</label>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.25rem" }}>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => handleImageUpload(e.target.files[0], "image_url")}
                      className="form-control"
                      style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem", flexGrow: "1" }}
                    />
                    {questionForm.image_url && (
                      <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                        <img
                          src={questionForm.image_url}
                          alt="Question Preview"
                          style={{ height: "30px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }}
                        />
                        <button
                          type="button"
                          onClick={() => setQuestionForm({ ...questionForm, image_url: "" })}
                          className="action-btn delete"
                          style={{ padding: "0.2rem" }}
                          title="Remove Image"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "1rem" }}>
                  <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <label className="form-label">Option A</label>
                    <input
                      className="form-control"
                      type="text"
                      value={questionForm.option_a}
                      onChange={(e) => setQuestionForm({ ...questionForm, option_a: e.target.value })}
                      required
                    />
                    <label style={{ fontSize: "0.85rem", fontWeight: "500", color: "var(--text-muted)", marginTop: "0.25rem" }}>Option A Image (Optional)</label>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e.target.files[0], "option_a_image_url")}
                        className="form-control"
                        style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem", flexGrow: "1" }}
                      />
                      {questionForm.option_a_image_url && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          <img
                            src={questionForm.option_a_image_url}
                            alt="Preview A"
                            style={{ height: "30px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }}
                          />
                          <button
                            type="button"
                            onClick={() => setQuestionForm({ ...questionForm, option_a_image_url: "" })}
                            className="action-btn delete"
                            style={{ padding: "0.2rem" }}
                            title="Remove Image"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <label className="form-label">Option B</label>
                    <input
                      className="form-control"
                      type="text"
                      value={questionForm.option_b}
                      onChange={(e) => setQuestionForm({ ...questionForm, option_b: e.target.value })}
                      required
                    />
                    <label style={{ fontSize: "0.85rem", fontWeight: "500", color: "var(--text-muted)", marginTop: "0.25rem" }}>Option B Image (Optional)</label>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e.target.files[0], "option_b_image_url")}
                        className="form-control"
                        style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem", flexGrow: "1" }}
                      />
                      {questionForm.option_b_image_url && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          <img
                            src={questionForm.option_b_image_url}
                            alt="Preview B"
                            style={{ height: "30px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }}
                          />
                          <button
                            type="button"
                            onClick={() => setQuestionForm({ ...questionForm, option_b_image_url: "" })}
                            className="action-btn delete"
                            style={{ padding: "0.2rem" }}
                            title="Remove Image"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "1rem" }}>
                  <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <label className="form-label">Option C</label>
                    <input
                      className="form-control"
                      type="text"
                      value={questionForm.option_c}
                      onChange={(e) => setQuestionForm({ ...questionForm, option_c: e.target.value })}
                      required
                    />
                    <label style={{ fontSize: "0.85rem", fontWeight: "500", color: "var(--text-muted)", marginTop: "0.25rem" }}>Option C Image (Optional)</label>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e.target.files[0], "option_c_image_url")}
                        className="form-control"
                        style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem", flexGrow: "1" }}
                      />
                      {questionForm.option_c_image_url && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          <img
                            src={questionForm.option_c_image_url}
                            alt="Preview C"
                            style={{ height: "30px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }}
                          />
                          <button
                            type="button"
                            onClick={() => setQuestionForm({ ...questionForm, option_c_image_url: "" })}
                            className="action-btn delete"
                            style={{ padding: "0.2rem" }}
                            title="Remove Image"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <label className="form-label">Option D</label>
                    <input
                      className="form-control"
                      type="text"
                      value={questionForm.option_d}
                      onChange={(e) => setQuestionForm({ ...questionForm, option_d: e.target.value })}
                      required
                    />
                    <label style={{ fontSize: "0.85rem", fontWeight: "500", color: "var(--text-muted)", marginTop: "0.25rem" }}>Option D Image (Optional)</label>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e.target.files[0], "option_d_image_url")}
                        className="form-control"
                        style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem", flexGrow: "1" }}
                      />
                      {questionForm.option_d_image_url && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          <img
                            src={questionForm.option_d_image_url}
                            alt="Preview D"
                            style={{ height: "30px", objectFit: "contain", borderRadius: "2px", border: "1px solid var(--border)" }}
                          />
                          <button
                            type="button"
                            onClick={() => setQuestionForm({ ...questionForm, option_d_image_url: "" })}
                            className="action-btn delete"
                            style={{ padding: "0.2rem" }}
                            title="Remove Image"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Part</label>
                    <select
                      className="form-control form-select"
                      value={questionForm.part_code}
                      onChange={(e) => setQuestionForm({ ...questionForm, part_code: e.target.value })}
                      required
                    >
                      <option value="A">Part A - Quantitative Ability</option>
                      <option value="B">Part B - Analytical Reasoning</option>
                      <option value="C">Part C - Logical Reasoning</option>
                      <option value="D">Part D - Computer Awareness</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Source S. No</label>
                    <input
                      className="form-control"
                      type="number"
                      placeholder="e.g. 1"
                      value={questionForm.source_s_no}
                      onChange={(e) => setQuestionForm({ ...questionForm, source_s_no: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Correct Option</label>
                    <select
                      className="form-control form-select"
                      value={questionForm.correct_option}
                      onChange={(e) => setQuestionForm({ ...questionForm, correct_option: e.target.value })}
                      required
                    >
                      <option value="A">Option A</option>
                      <option value="B">Option B</option>
                      <option value="C">Option C</option>
                      <option value="D">Option D</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Marks</label>
                    <input
                      className="form-control"
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={questionForm.marks}
                      onChange={(e) => setQuestionForm({ ...questionForm, marks: parseFloat(e.target.value) })}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setQuestionModal({ show: false, editId: null })}
                  style={{ width: "100px" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={actionLoading}
                  style={{ width: "130px" }}
                >
                  {actionLoading ? "Saving..." : "Save Question"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin Reopen Attempt Modal */}
      {reopenModal.show && (
        <div className="modal-backdrop">
          <div className="modal-content animate-slide-up" style={{ maxWidth: "450px" }}>
            <div className="modal-header">
              <h2 className="modal-title">Reopen Exam Attempt</h2>
            </div>
            <form onSubmit={handleReopenAttemptSubmit}>
              <div className="modal-body">
                <p style={{ marginBottom: "1rem", fontWeight: "600" }}>
                  Reopening exam session for: <span style={{ color: "var(--primary)" }}>{reopenModal.candidateName}</span>
                </p>
                <div className="alert alert-warning" style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
                  <strong>⚠️ Warning:</strong> This will allow the candidate to continue from saved answers. Existing answers will not be deleted.
                </div>
                <div className="form-group" style={{ marginBottom: "1rem" }}>
                  <label className="form-label">Reopen Reason (Required)</label>
                  <textarea
                    className="form-control"
                    rows="3"
                    placeholder="Enter reason (e.g., Accidental submit, power shutdown review...)"
                    value={reopenModal.reason}
                    onChange={(e) => setReopenModal({ ...reopenModal, reason: e.target.value })}
                    required
                  ></textarea>
                </div>
                <div className="form-group">
                  <label className="form-label">Time Extension (Minutes - Optional)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    placeholder="0"
                    value={reopenModal.timeExtension}
                    onChange={(e) => setReopenModal({ ...reopenModal, timeExtension: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setReopenModal({ show: false, attemptId: null, candidateName: "", reason: "", timeExtension: 0 })}
                  style={{ width: "100px" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={actionLoading}
                  style={{ width: "150px" }}
                >
                  {actionLoading ? "Reopening..." : "Reopen Attempt"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin Force Submit Attempt Modal */}
      {forceSubmitModal.show && (
        <div className="modal-backdrop">
          <div className="modal-content animate-slide-up" style={{ maxWidth: "450px" }}>
            <div className="modal-header">
              <h2 className="modal-title" style={{ color: "#dc2626" }}>Force Submit Attempt</h2>
            </div>
            <form onSubmit={handleForceSubmitAttemptSubmit}>
              <div className="modal-body">
                <p style={{ marginBottom: "1.25rem", fontWeight: "600" }}>
                  Force submit exam session for: <span style={{ color: "#dc2626" }}>{forceSubmitModal.candidateName}</span>
                </p>
                <div className="form-group">
                  <label className="form-label">Submission Reason / Notes</label>
                  <textarea
                    className="form-control"
                    rows="3"
                    placeholder="Enter reason for force submission..."
                    value={forceSubmitModal.reason}
                    onChange={(e) => setForceSubmitModal({ ...forceSubmitModal, reason: e.target.value })}
                  ></textarea>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setForceSubmitModal({ show: false, attemptId: null, candidateName: "", reason: "" })}
                  style={{ width: "100px" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-danger"
                  disabled={actionLoading}
                  style={{ width: "150px", backgroundColor: "#dc2626", borderColor: "#dc2626" }}
                >
                  {actionLoading ? "Submitting..." : "Force Submit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
