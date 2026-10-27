import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ListTodo, Plus } from "lucide-react";
import { api, apiPatch, apiPost } from "../api/client.js";
import { Button, Input } from "../components/ui.jsx";
import "../styles/pages.css";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api("/api/projects"),
  });
  const project = projects.find((p) => p.id === projectId);

  const { data: tasks = [] } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => api(`/api/tasks?project_id=${projectId}`),
  });

  const addTask = useMutation({
    mutationFn: () => apiPost("/api/tasks", { title: title || "Untitled task", project_id: projectId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      setTitle("");
      setAdding(false);
    },
  });

  const toggle = useMutation({
    mutationFn: (t) => apiPatch(`/api/tasks/${t.id}`, { status: t.status === "done" ? "todo" : "done" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", projectId] }),
  });

  return (
    <div className="page page-narrow">
      <div className="editor-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate("/projects")}>
          <ArrowLeft size={14} /> Projects
        </button>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{project?.name || "Project"}</h1>
          {project?.description && <p className="page-subtitle">{project.description}</p>}
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setAdding(true)}>
          Add task
        </Button>
      </div>

      {adding && (
        <div className="note-create" style={{ marginBottom: 16, display: "flex", gap: 8 }}>
          <Input autoFocus placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button variant="primary" onClick={() => addTask.mutate()}>Add</Button>
        </div>
      )}

      <div className="card">
        {tasks.length === 0 ? (
          <div className="card-row" style={{ color: "var(--text-muted)" }}>
            <ListTodo size={15} className="home-row-icon" /> No tasks in this project yet.
          </div>
        ) : (
          tasks.map((t) => (
            <div key={t.id} className="card-row">
              <input type="checkbox" className="task-check" checked={t.status === "done"} onChange={() => toggle.mutate(t)} />
              <span className={`task-title ${t.status === "done" ? "task-title-done" : ""}`}>{t.title}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
