import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { AuthProvider } from "./lib/auth";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Chat from "./pages/Chat";
import Programmes from "./pages/Programmes";
import ProgrammeDetail from "./pages/ProgrammeDetail";
import Eligibility from "./pages/Eligibility";
import Dashboard from "./pages/Dashboard";
import Policies from "./pages/Policies";
import Admin from "./pages/Admin";
import Login from "./pages/Login";

// University logos/photos live in public/brand/, which is not committed (official brand assets).
// On a fresh clone they are missing, so hide broken images instead of showing broken-image icons.
window.addEventListener("error", e => {
  const t = e.target;
  if (t instanceof HTMLImageElement && t.src.includes("/brand/")) t.style.visibility = "hidden";
}, true);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Landing />} />
            <Route path="chat" element={<Chat />} />
            <Route path="programmes" element={<Programmes />} />
            <Route path="programmes/:id" element={<ProgrammeDetail />} />
            <Route path="eligibility" element={<Eligibility />} />
            <Route path="fees" element={<Policies only={["fees", "scholarship"]} eyebrow="Fees" title="Fees, refunds & scholarships" photo="hostel-court.jpg"
              asks={["How do merit scholarships work and how are they renewed?", "What is the fee refund policy if I withdraw?", "What are the hostel fees?"]} />} />
            <Route path="academics" element={<Policies only={["academic_rules", "attendance", "conduct", "exam"]} eyebrow="Navigate Bennett" title="Academic rules & regulations" photo="seminar.jpg"
              asks={["What is the minimum attendance for end-semester exams?", "What are the penalties for unfair means?", "How is CGPA calculated?", "Can I change my stream?"]} />} />
            <Route path="calendar" element={<Policies only={["calendar", "exam"]} eyebrow="Navigate Bennett" title="Academic calendar & examinations" photo="campus-evening.jpg"
              asks={["When do end-semester exams start this semester?", "How do I apply for re-evaluation?", "What are the holidays this semester?"]} />} />
            <Route path="policies" element={<Policies />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="admin" element={<Admin />} />
            <Route path="login" element={<Login />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
