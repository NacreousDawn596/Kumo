import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, Plus, Users, Video } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, EmptyState, IconButton } from "../components/ui.jsx";
import GroupCallBar from "../components/GroupCallBar.jsx";
import "../styles/pages.css";
import "./sessions.css";

export default function StudyRoomPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api(`/api/sessions/${sessionId}`),
  });

  const { data: files = [] } = useQuery({
    queryKey: ["files"],
    queryFn: () => api("/api/vault/files"),
  });

  const createWhiteboard = useMutation({
    mutationFn: () => apiPost("/api/whiteboards", { name: `${session?.name || "Session"} — whiteboard`, session_id: sessionId }),
    onSuccess: (wb) => navigate(`/whiteboards/${wb.id}`),
  });

  const addResource = useMutation({
    mutationFn: (fileId) => apiPost(`/api/sessions/${sessionId}/resources?resource_type=file&resource_id=${fileId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
  });

  const join = useMutation({
    mutationFn: () => apiPost(`/api/sessions/${sessionId}/join`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
  });

  const isMember = session?.members?.length > 0;
  const whiteboards = session?.resources?.filter((r) => r.resource_type === "whiteboard") || [];
  const linkedFiles = session?.resources?.filter((r) => r.resource_type === "file") || [];

  return (
    <div className="page page-narrow">
      <div className="editor-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate("/sessions")}>
          <ArrowLeft size={14} /> Study Rooms
        </button>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{session?.name || "Study room"}</h1>
          <p className="page-subtitle">
            {session?.members?.length || 0} participant{(session?.members?.length || 0) === 1 ? "" : "s"} · {session?.status}
          </p>
        </div>
        <div className="page-actions">
          {!isMember && <Button variant="secondary" onClick={() => join.mutate()}>Join</Button>}
          <Button variant="primary" icon={Plus} loading={createWhiteboard.isPending} onClick={() => createWhiteboard.mutate()}>
            New whiteboard
          </Button>
        </div>
      </div>

      <GroupCallBar sessionId={sessionId} />

      <div className="room-grid">
        <section className="section">
          <h2 className="section-title">Whiteboards</h2>
          {whiteboards.length === 0 ? (
            <EmptyState
              icon={Video}
              title="No whiteboards yet"
              description="Create a whiteboard to start solving problems together."
              action={<Button variant="primary" icon={Plus} onClick={() => createWhiteboard.mutate()}>New whiteboard</Button>}
            />
          ) : (
            <div className="card">
              {whiteboards.map((r) => (
                <button key={r.resource_id} className="card-row" onClick={() => navigate(`/whiteboards/${r.resource_id}`)}>
                  <Video size={15} className="home-row-icon" />
                  <span className="note-title">Open whiteboard</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="section">
          <h2 className="section-title">Documents</h2>
          {linkedFiles.length === 0 ? (
            <p className="home-muted">Link a document from your vault to share it here.</p>
          ) : (
            <div className="card">
              {linkedFiles.map((r) => (
                <button key={r.resource_id} className="card-row" onClick={() => navigate(`/documents/${r.resource_id}`)}>
                  <FileText size={15} className="home-row-icon" />
                  <span className="note-title">Open document</span>
                </button>
              ))}
            </div>
          )}
          <div style={{ marginTop: 12 }}>
            <h3 className="room-sub">Add from vault</h3>
            <div className="room-file-list">
              {files.slice(0, 8).map((f) => (
                <button key={f.id} className="room-file" onClick={() => addResource.mutate(f.id)}>
                  <FileText size={14} />
                  <span>{f.name}</span>
                  <Plus size={14} />
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Participants</h2>
          <div className="card">
            {(session?.members || []).map((uid) => (
              <div key={uid} className="card-row">
                <Users size={15} className="home-row-icon" />
                <span className="note-title">{uid === session?.owner_id ? "Organizer" : "Participant"}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
