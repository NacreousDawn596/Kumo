import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, Plus, MessageSquare } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input, Textarea } from "../components/ui.jsx";
import "../styles/pages.css";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: groups = [] } = useQuery({
    queryKey: ["groups"],
    queryFn: () => api("/api/groups"),
  });

  const create = useMutation({
    mutationFn: () => apiPost("/api/groups", { name, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      setCreating(false);
      setName("");
      setDescription("");
    },
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Groups</h1>
          <p className="page-subtitle">{groups.length} group{groups.length === 1 ? "" : "s"}</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New group
        </Button>
      </div>

      {groups.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No groups yet"
          description="Create a study group to collaborate with classmates."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Create a group</Button>}
        />
      ) : (
        <div className="card">
          {groups.map((g) => (
            <Link key={g.id} to={`/groups/${g.id}`} className="card-row">
              <div className="notif-main">
                <div className="note-title">{g.name}</div>
                {g.description && <div className="notif-body">{g.description}</div>}
                <div className="notif-time">
                  {g.members.length} member{g.members.length === 1 ? "" : "s"} · you are {g.my_role}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New group"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Group name" value={name} onChange={(e) => setName(e.target.value)} />
          <Textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
      </Dialog>
    </div>
  );
}
