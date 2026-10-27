import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Link2, MessageSquare, Plus, Users, X } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, EmptyState, Input } from "../components/ui.jsx";
import "../styles/pages.css";

export default function GroupDetailPage() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [inviteUrl, setInviteUrl] = useState(null);

  const { data: group } = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => api(`/api/groups/${groupId}`),
  });

  const { data: invitations = [] } = useQuery({
    queryKey: ["invitations", groupId],
    queryFn: () => api(`/api/groups/${groupId}/invitations`).catch(() => []),
  });

  const generateLink = useMutation({
    mutationFn: () => apiPost(`/api/groups/${groupId}/invite-link`),
    onSuccess: (res) => {
      const url = `${window.location.origin}${res.url}`;
      setInviteUrl(url);
      navigator.clipboard?.writeText(url);
    },
  });

  const addMember = useMutation({
    mutationFn: (userId) => apiPost(`/api/groups/${groupId}/members`, { user_id: userId, role: "member" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      setAddOpen(false);
      setQuery("");
      setResults([]);
    },
  });

  const approve = useMutation({
    mutationFn: (rid) => apiPost(`/api/groups/requests/${rid}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      queryClient.invalidateQueries({ queryKey: ["invitations", groupId] });
    },
  });

  const reject = useMutation({
    mutationFn: (rid) => apiPost(`/api/groups/requests/${rid}/reject`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invitations", groupId] }),
  });

  const searchUsers = async (q) => {
    setQuery(q);
    if (q.length < 1) return setResults([]);
    setResults(await api(`/api/users/search?q=${encodeURIComponent(q)}`));
  };

  const pending = invitations.filter((i) => i.status === "pending");
  const canManage = group?.my_role === "owner" || group?.my_role === "admin";

  return (
    <div className="page page-narrow">
      <div className="editor-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate("/groups")}>
          <ArrowLeft size={14} /> Groups
        </button>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{group?.name || "Group"}</h1>
          {group?.description && <p className="page-subtitle">{group.description}</p>}
          <p className="page-subtitle">{group?.members?.length || 0} members · you are {group?.my_role}</p>
        </div>
        <div className="page-actions">
          <Link to="/messages" className="btn btn-secondary">
            <MessageSquare size={15} /> Chat
          </Link>
          {canManage && (
            <Button variant="primary" icon={Plus} onClick={() => setAddOpen(true)}>
              Add member
            </Button>
          )}
        </div>
      </div>

      {canManage && (
        <div className="section">
          <h2 className="section-title">Invite link</h2>
          <div className="share-link-row">
            <Input
              readOnly
              placeholder="Generate an invite link…"
              value={inviteUrl || ""}
              onFocus={(e) => e.target.select()}
            />
            <Button variant="secondary" icon={Link2} onClick={() => generateLink.mutate()}>
              {inviteUrl ? "Copy" : "Generate"}
            </Button>
          </div>
        </div>
      )}

      {canManage && pending.length > 0 && (
        <div className="section">
          <h2 className="section-title">Join requests ({pending.length})</h2>
          <div className="card">
            {pending.map((r) => (
              <div key={r.id} className="card-row">
                <Users size={15} className="home-row-icon" />
                <span className="note-title">{r.email || r.invitee_id || "Member"}</span>
                <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={() => approve.mutate(r.id)}>
                    <Check size={14} /> Approve
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => reject.mutate(r.id)}>
                    <X size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="section">
        <h2 className="section-title">Members</h2>
        <div className="card">
          {(group?.members || []).map((m) => (
            <div key={m.user_id} className="card-row">
              <Users size={15} className="home-row-icon" />
              <span className="note-title">{m.user_id === group?.owner_id ? "Owner" : m.role}</span>
            </div>
          ))}
        </div>
      </div>

      {addOpen && (
        <div className="dialog-overlay" onMouseDown={() => setAddOpen(false)}>
          <div className="dialog" style={{ maxWidth: 420 }} onMouseDown={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h2 className="dialog-title">Add member</h2>
            </div>
            <div className="dialog-body">
              <Input autoFocus placeholder="Search by name or username…" value={query} onChange={(e) => searchUsers(e.target.value)} />
              <div className="transfer-results">
                {results.map((u) => (
                  <button key={u.id} className="transfer-result" onClick={() => addMember.mutate(u.id)}>
                    <span>{u.display_name}</span>
                    <span className="transfer-result-user">@{u.username}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
