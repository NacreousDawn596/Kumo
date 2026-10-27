import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import { ArrowRight, Calendar, FileText, Folder, ListTodo, MessageSquare, Video } from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../store/auth.js";
import "../styles/pages.css";
import "./home.css";

function Section({ title, link, linkLabel, children }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">{title}</h2>
        {link && (
          <Link to={link} className="section-link">
            {linkLabel || "View all"} <ArrowRight size={13} />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const today = new Date();
  const todayIso = format(today, "yyyy-MM-dd");

  const { data: events = [] } = useQuery({
    queryKey: ["events", todayIso],
    queryFn: () => api(`/api/calendar?start=${todayIso}T00:00:00Z`),
  });
  const { data: tasks = [] } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api("/api/tasks"),
  });
  const { data: pages = [] } = useQuery({
    queryKey: ["pages"],
    queryFn: () => api("/api/pages"),
  });
  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api("/api/conversations"),
  });
  const { data: files = [] } = useQuery({
    queryKey: ["files"],
    queryFn: () => api("/api/vault/files"),
  });
  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api("/api/sessions"),
  });

  const dueSoon = tasks.filter((t) => t.status !== "done").slice(0, 5);
  const recentPages = pages.slice(0, 5);
  const recentFiles = files.slice(0, 5);
  const activeSessions = sessions.filter((s) => s.status !== "ended").slice(0, 4);
  const recentConvos = conversations.slice(0, 5);

  const hour = today.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const isNew = pages.length === 0 && tasks.length === 0 && files.length === 0;

  return (
    <div className="page">
      <div className="home-hero">
        <div>
          <h1 className="home-greeting">
            {greeting}, {user?.display_name?.split(" ")[0]}.
          </h1>
          <p className="home-date">{format(today, "EEEE, MMMM d")}</p>
        </div>
      </div>

      {isNew && (
        <div className="home-welcome">
          <h3>Welcome to Kumo</h3>
          <p>
            Your notes, files, tasks, and study rooms live together here. Start by
            capturing a note or creating a task.
          </p>
          <div className="home-welcome-actions">
            <Link className="btn btn-primary" to="/notes">Create a note</Link>
            <Link className="btn btn-secondary" to="/tasks">Add a task</Link>
          </div>
        </div>
      )}

      <div className="home-grid">
        <div className="home-col">
          <Section title="Today" link="/calendar">
            {events.length === 0 ? (
              <p className="home-muted">No events today.</p>
            ) : (
              <div className="home-list">
                {events.slice(0, 5).map((e) => (
                  <div key={e.id} className="home-row">
                    <Calendar size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{e.title}</div>
                      <div className="home-row-meta">
                        {e.all_day ? "All day" : format(new Date(e.start_at), "h:mm a")}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Due soon" link="/tasks">
            {dueSoon.length === 0 ? (
              <p className="home-muted">Nothing due soon.</p>
            ) : (
              <div className="home-list">
                {dueSoon.map((t) => (
                  <div key={t.id} className="home-row">
                    <ListTodo size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{t.title}</div>
                      {t.due_date && (
                        <div className="home-row-meta">Due {format(new Date(t.due_date), "MMM d")}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Recent notes" link="/notes">
            {recentPages.length === 0 ? (
              <p className="home-muted">No notes yet.</p>
            ) : (
              <div className="home-list">
                {recentPages.map((p) => (
                  <Link key={p.id} to={`/pages/${p.id}`} className="home-row">
                    <FileText size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{p.title}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </div>

        <div className="home-col">
          <Section title="Recent documents" link="/vault">
            {recentFiles.length === 0 ? (
              <p className="home-muted">No documents yet.</p>
            ) : (
              <div className="home-list">
                {recentFiles.map((f) => (
                  <Link key={f.id} to="/vault" className="home-row">
                    <Folder size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{f.name}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>

          <Section title="Active study sessions" link="/sessions">
            {activeSessions.length === 0 ? (
              <p className="home-muted">No active sessions.</p>
            ) : (
              <div className="home-list">
                {activeSessions.map((s) => (
                  <Link key={s.id} to="/sessions" className="home-row">
                    <Video size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{s.name}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>

          <Section title="Recent conversations" link="/messages">
            {recentConvos.length === 0 ? (
              <p className="home-muted">No conversations yet.</p>
            ) : (
              <div className="home-list">
                {recentConvos.map((c) => (
                  <Link key={c.id} to={`/messages/${c.id}`} className="home-row">
                    <MessageSquare size={15} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">
                        {c.title || c.other_user_ids.join(", ")}
                      </div>
                      {c.last_message && (
                        <div className="home-row-meta">{c.last_message.body}</div>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
