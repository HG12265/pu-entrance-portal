import React from "react";
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import StudentLogin from "./pages/StudentLogin";
import VerifyDetails from "./pages/VerifyDetails";
import Instructions from "./pages/Instructions";
import Exam from "./pages/Exam";
import Result from "./pages/Result";
import Leaderboard from "./pages/Leaderboard";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import UniversityHeader from "./components/UniversityHeader";
import api from "./api";

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();

  React.useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          if (localStorage.getItem("student_token")) {
            localStorage.removeItem("student_token");
            localStorage.removeItem("student_session");
            localStorage.removeItem("exam_status");
            localStorage.removeItem("attempt_id");
            localStorage.removeItem("submit_result");
            navigate("/", { state: { message: "Session expired. Please login again." } });
          }
        }
        return Promise.reject(error);
      }
    );
    return () => {
      api.interceptors.response.eject(interceptor);
    };
  }, [navigate]);

  const headerRoutes = ["/", "/instructions", "/result", "/leaderboard", "/verify-details"];
  const showUniversityHeader = headerRoutes.includes(location.pathname);
  const isAdminRoute = location.pathname.startsWith("/admin");
  const isExamRoute = location.pathname === "/exam";

  // Apply a class wrapper to adjust heights in CSS when UniversityHeader is shown
  const wrapperClass = showUniversityHeader ? "app-container has-univ-header" : "app-container";

  return (
    <div className={wrapperClass}>
      {/* Headers conditional rendering */}
      {showUniversityHeader && <UniversityHeader />}
      
      {isAdminRoute && !isExamRoute && (
        <nav className="navbar">
          <div className="nav-brand">
            <div className="nav-logo-text">
              <h1>PERIYAR UNIVERSITY</h1>
              <p>Entrance Examination Management System</p>
            </div>
          </div>
          <div className="nav-links">
            <Link to="/" className="nav-link">Portal Home</Link>
          </div>
        </nav>
      )}

      {/* Main Content Area */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<StudentLogin />} />
          <Route path="/verify-details" element={<VerifyDetails />} />
          <Route path="/instructions" element={<Instructions />} />
          <Route path="/exam" element={<Exam />} />
          <Route path="/result" element={<Result />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route 
            path="/admin/dashboard" 
            element={
              <ProtectedRoute>
                <AdminDashboard />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </main>

      {/* Footer */}
      {!isExamRoute && (
        <footer style={{ backgroundColor: "var(--primary-dark)", color: "#64748b", textAlign: "center", padding: "1.5rem", fontSize: "0.85rem", borderTop: "1px solid rgba(255, 255, 255, 0.05)" }}>
          &copy; {new Date().getFullYear()} Periyar University Entrance Examination Portal. All Rights Reserved.
        </footer>
      )}
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
