import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Plus, Video } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input } from "../components/ui.jsx";
import "../styles/pages.css";

export default function SessionsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api("/api/sessions"),
  });

  const create = useMutation({
    mutationFn: () => apiPost("/api/sessions", { name: name || "Study session" }),
    onSuccess: (s) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setCreating(false);
      setName("");
      navigate(`/sessions/${s.id}`);
    },
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Study Rooms</h1>
          <p className="page-subtitle">Collaborative sessions with PDFs, whiteboards, and chat.</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New session
        </Button>
      </div>

      {sessions.length === 0 ? (
        <EmptyState
          icon={Video}
          title="No study rooms yet"
          description="Start a session to study a document together."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Start a session</Button>}
        />
      ) : (
        <div className="card">
          {sessions.map((s) => (
            <Link key={s.id} to={`/sessions/${s.id}`} className="card-row">
              <Video size={15} className="home-row-icon" />
              <div className="notif-main">
                <div className="note-title">{s.name}</div>
                <div className="notif-time">{s.members.length} participants · {s.status}</div>
              </div>
              <ArrowRight size={15} className="home-row-icon" />
            </Link>
          ))}
        </div>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New study session"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <Input autoFocus placeholder="Session name" value={name} onChange={(e) => setName(e.target.value)} />
      </Dialog>
    </div>
  );
}
