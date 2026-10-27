import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input, Textarea } from "../components/ui.jsx";
import "../styles/pages.css";

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api("/api/projects"),
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api("/api/tasks"),
  });

  const create = useMutation({
    mutationFn: () => apiPost("/api/projects", { name, description }),
    onSuccess: (p) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      setName("");
      setDescription("");
      navigate(`/projects/${p.id}`);
    },
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">{projects.length} project{projects.length === 1 ? "" : "s"}</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New project
        </Button>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Group tasks, notes, and files under a project."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Create a project</Button>}
        />
      ) : (
        <div className="card">
          {projects.map((p) => {
            const count = tasks.filter((t) => t.project_id === p.id).length;
            return (
              <Link key={p.id} to={`/projects/${p.id}`} className="card-row">
                <FolderKanban size={15} className="home-row-icon" />
                <div className="notif-main">
                  <div className="note-title">{p.name}</div>
                  {p.description && <div className="notif-body">{p.description}</div>}
                  <div className="notif-time">{count} task{count === 1 ? "" : "s"}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New project"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} />
          <Textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
      </Dialog>
    </div>
  );
}
