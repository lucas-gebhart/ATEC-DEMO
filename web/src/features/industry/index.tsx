// WS1 owns this folder: company profile, new test request form, my requests + status.
import { Navigate, Route, Routes } from "react-router-dom";
import "./industry.css";
import MyRequests from "./MyRequests";
import NewRequest from "./NewRequest";
import CompanyProfile from "./CompanyProfile";
import RequestDetail from "./RequestDetail";

export default function IndustryHome() {
  return (
    <Routes>
      <Route index element={<MyRequests />} />
      <Route path="new" element={<NewRequest />} />
      <Route path="company" element={<CompanyProfile />} />
      <Route path="requests/:id" element={<RequestDetail />} />
      <Route path="*" element={<Navigate to="/industry" replace />} />
    </Routes>
  );
}
