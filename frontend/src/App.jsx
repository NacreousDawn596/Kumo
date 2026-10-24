import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./store/auth.js";
import { useTheme } from "./store/theme.js";
import AppShell from "./layout/AppShell.jsx";
import { Spinner } from "./components/ui.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import InboxPage from "./pages/InboxPage.jsx";
import CalendarPage from "./pages/CalendarPage.jsx";
import TasksPage from "./pages/TasksPage.jsx";
import NotesPage from "./pages/NotesPage.jsx";
import PageEditorPage from "./pages/PageEditorPage.jsx";
import KnowledgePage from "./pages/KnowledgePage.jsx";
import VaultPage from "./pages/VaultPage.jsx";
import SessionsPage from "./pages/SessionsPage.jsx";
import GroupsPage from "./pages/GroupsPage.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import WhiteboardPage from "./pages/WhiteboardPage.jsx";
import DocumentPage from "./pages/DocumentPage.jsx";
import MessagesPage from "./pages/MessagesPage.jsx";

function FullPageLoader() {
  return (
    <div className="fullpage-loader">
      <Spinner size={22} />
    </div>
  );
}

function Protected({ children }) {
  const { user, initialized } = useAuth();
  const location = useLocation();
  if (!initialized) return <FullPageLoader />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

export default function App() {
  const loadUser = useAuth((s) => s.loadUser);
  const { preference } = useTheme();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      preference === "system"
        ? window.matchMedia("(prefers-color-scheme: light)").matches
          ? "light"
          : "dark"
        : preference
    );
  }, [preference]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/"
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="messages/:conversationId" element={<MessagesPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="notes" element={<NotesPage />} />
        <Route path="pages/:pageId" element={<PageEditorPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="vault" element={<VaultPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="groups/:groupId" element={<GroupsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="settings/:section" element={<SettingsPage />} />
        <Route path="whiteboards/:whiteboardId" element={<WhiteboardPage />} />
        <Route path="documents/:fileId" element={<DocumentPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
