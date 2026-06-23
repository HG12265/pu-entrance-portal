import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const Leaderboard = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const studentToken = localStorage.getItem("student_token");
    if (studentToken) {
      navigate("/result");
    } else {
      navigate("/");
    }
  }, [navigate]);

  return (
    <div className="centered-container">
      <div className="spinner"></div>
    </div>
  );
};

export default Leaderboard;
