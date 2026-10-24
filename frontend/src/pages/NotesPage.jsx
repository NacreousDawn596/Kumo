import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { FileText, Plus } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input } from "../components/ui.jsx";
import "../styles/pages.css";
import "./notes.css";

const TEMPLATES = [
  { id: "lecture_notes", label: "Lecture notes" },
  { id: "course_page", label: "Course page" },
  { id: "chapter_summary", label: "Chapter summary" },
  { id: "exercise_solutions", label: "Exercise solutions" },
  { id: "lab_report", label: "Lab report" },
  { id: "project_docs", label: "Project documentation" },
  { id: "meeting_notes", label: "Meeting notes" },
  { id: "revision_plan", label: "Revision plan" },
  { id: "study_session_notes", label: "Study-session notes" },
  { id: "research_notes", label: "Research notes" },
];

export default function NotesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [template, setTemplate] = useState(null);

  const { data: pages = [], isLoading } = useQuery({
    queryKey: ["pages"],
    queryFn: () => api("/api/pages"),
  });

  const create = useMutation({
    mutationFn: () => apiPost("/api/pages", { title: title || "Untitled", template }),
    onSuccess: (page) => {
      queryClient.invalidateQueries({ queryKey: ["pages"] });
      setCreating(false);
      setTitle("");
      setTemplate(null);
      navigate(`/pages/${page.id}`);
    },
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Notes</h1>
          <p className="page-subtitle">{pages.length} note{pages.length === 1 ? "" : "s"}</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New note
        </Button>
      </div>

      {isLoading ? null : pages.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No notes yet"
          description="Create your first note to start building your knowledge base."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Create a note</Button>}
        />
      ) : (
        <div className="notes-list">
          {pages.map((p) => (
            <Link key={p.id} to={`/pages/${p.id}`} className="note-item">
              <span className="note-icon">{p.icon || "📄"}</span>
              <div className="note-main">
                <span className="note-title">{p.title}</span>
                <span className="note-meta">
                  {p.has_children ? "Nested pages · " : ""}
                  {format(new Date(p.updated_at), "MMM d, yyyy")}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New note"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Note title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="template-label">Start from a template</div>
          <div className="template-grid">
            {TEMPLATES.map((t) => (
              <button
                key={t.id}
                className={`template-chip ${template === t.id ? "template-chip-active" : ""}`}
                onClick={() => setTemplate(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </Dialog>
    </div>
  );
}
