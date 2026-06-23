import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined && import.meta.env.VITE_API_BASE_URL !== null
  ? import.meta.env.VITE_API_BASE_URL
  : "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const isStudentRoute = 
      config.url.includes("/students") || 
      config.url.includes("/exams") || 
      config.url.includes("/results/my-results");
    
    const studentToken = localStorage.getItem("student_token");
    const adminToken = localStorage.getItem("admin_token");
    
    if (isStudentRoute && studentToken) {
      config.headers.Authorization = `Bearer ${studentToken}`;
    } else if (adminToken) {
      config.headers.Authorization = `Bearer ${adminToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
export { API_BASE_URL };
