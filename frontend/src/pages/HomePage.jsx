import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import { ArrowRight, Calendar, FileText, Folder, ListTodo, MessageSquare, Plus, Video } from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../store/auth.js";
import { Button } from "../components/ui.jsx";
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

function EmptySection({ text, to, action }) {
  return (
    <div className="home-empty">
      <p className="home-empty-text">{text}</p>
      {to && (
        <Link to={to} className="home-empty-action">
          {action}
        </Link>
      )}
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const today = new Date();
  const todayIso = format(today, "yyyy-MM-dd");

  const { data: events = [] } = useQuery({
    queryKey: ["events", todayIso],
    queryFn: () => api(`/api/calendar?start=${todayIso}T00:00:00Z`),
  });
  const { data: tasks = [] } = useQuery({ queryKey: ["tasks"], queryFn: () => api("/api/tasks") });
  const { data: pages = [] } = useQuery({ queryKey: ["pages"], queryFn: () => api("/api/pages") });
  const { data: conversations = [] } = useQuery({ queryKey: ["conversations"], queryFn: () => api("/api/conversations") });
  const { data: files = [] } = useQuery({ queryKey: ["files"], queryFn: () => api("/api/vault/files") });
  const { data: sessions = [] } = useQuery({ queryKey: ["sessions"], queryFn: () => api("/api/sessions") });

  const dueSoon = tasks.filter((t) => t.status !== "done").slice(0, 6);
  const recentPages = pages.slice(0, 6);
  const recentFiles = files.slice(0, 5);
  const activeSessions = sessions.filter((s) => s.status !== "ended").slice(0, 5);
  const recentConvos = conversations.slice(0, 5);

  const hour = today.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const firstName = user?.display_name?.split(" ")[0];
  const isNew = pages.length === 0 && tasks.length === 0 && files.length === 0;

  return (
    <div className="page home">
      <header className="home-hero">
        <div className="home-hero-text">
          <p className="home-date">{format(today, "EEEE, MMMM d")}</p>
          <h1 className="home-greeting">
            {greeting}, {firstName}.
          </h1>
        </div>
        <div className="home-hero-actions">
          <Button variant="secondary" icon={ListTodo} onClick={() => navigate("/tasks")}>
            New task
          </Button>
          <Button variant="primary" icon={Plus} onClick={() => navigate("/notes")}>
            New note
          </Button>
        </div>
      </header>

      {isNew && (
        <div className="home-onboarding">
          <h2 className="home-onboarding-title">Set up your workspace</h2>
          <p className="home-onboarding-text">
            Notes, files, tasks, and study rooms live together in Kumo. Start with
            one small step.
          </p>
          <div className="home-onboarding-actions">
            <Link className="btn btn-primary" to="/notes">Create your first note</Link>
            <Link className="btn btn-secondary" to="/vault">Upload a document</Link>
            <Link className="btn btn-ghost" to="/groups">Join a study group</Link>
          </div>
        </div>
      )}

      <div className="home-grid">
        <div className="home-col home-col-main">
          <Section title="Today" link="/calendar" linkLabel="Calendar">
            {events.length === 0 ? (
              <EmptySection text="Nothing scheduled for today." to="/calendar" action="Add event" />
            ) : (
              <div className="home-list">
                {events.slice(0, 6).map((e) => (
                  <div key={e.id} className="home-row">
                    <Calendar size={16} className="home-row-icon" />
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

          <Section title="Tasks" link="/tasks">
            {dueSoon.length === 0 ? (
              <EmptySection text="No tasks need your attention." to="/tasks" action="Add a task" />
            ) : (
              <div className="home-list">
                {dueSoon.map((t) => (
                  <div key={t.id} className="home-row">
                    <ListTodo size={16} className="home-row-icon" />
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
              <EmptySection text="Your notes will appear here." to="/notes" action="Create a note" />
            ) : (
              <div className="home-list">
                {recentPages.map((p) => (
                  <Link key={p.id} to={`/pages/${p.id}`} className="home-row">
                    <FileText size={16} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{p.title}</div>
                      <div className="home-row-meta">{format(new Date(p.updated_at), "MMM d")}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </div>

        <div className="home-col home-col-side">
          <Section title="Recent documents" link="/vault">
            {recentFiles.length === 0 ? (
              <EmptySection text="Uploaded documents will appear here." to="/vault" action="Upload a file" />
            ) : (
              <div className="home-list">
                {recentFiles.map((f) => (
                  <Link key={f.id} to="/vault" className="home-row">
                    <Folder size={16} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{f.name}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>

          <Section title="Study rooms" link="/sessions">
            {activeSessions.length === 0 ? (
              <EmptySection text="No active study sessions." to="/sessions" action="Start a session" />
            ) : (
              <div className="home-list">
                {activeSessions.map((s) => (
                  <Link key={s.id} to="/sessions" className="home-row">
                    <Video size={16} className="home-row-icon" />
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
              <EmptySection text="Conversations will appear here." to="/messages" action="Open messages" />
            ) : (
              <div className="home-list">
                {recentConvos.map((c) => (
                  <Link key={c.id} to={`/messages/${c.id}`} className="home-row">
                    <MessageSquare size={16} className="home-row-icon" />
                    <div className="home-row-main">
                      <div className="home-row-title">{c.title || c.other_user_ids.join(", ")}</div>
                      {c.last_message && <div className="home-row-meta">{c.last_message.body}</div>}
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
