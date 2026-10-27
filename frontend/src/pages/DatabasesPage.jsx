import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Table } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input } from "../components/ui.jsx";
import "../styles/pages.css";

export default function DatabasesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const { data: databases = [] } = useQuery({
    queryKey: ["databases"],
    queryFn: () => api("/api/databases"),
  });

  const create = useMutation({
    mutationFn: () => apiPost("/api/databases", { name: name || "Untitled database" }),
    onSuccess: (d) => {
      queryClient.invalidateQueries({ queryKey: ["databases"] });
      setCreating(false);
      setName("");
      navigate(`/databases/${d.id}`);
    },
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Databases</h1>
          <p className="page-subtitle">Structured collections of typed records.</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New database
        </Button>
      </div>

      {databases.length === 0 ? (
        <EmptyState
          icon={Table}
          title="No databases yet"
          description="Create a database to organize courses, assignments, or research papers."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Create a database</Button>}
        />
      ) : (
        <div className="card">
          {databases.map((d) => (
            <Link key={d.id} to={`/databases/${d.id}`} className="card-row">
              <Table size={15} className="home-row-icon" />
              <span className="note-title">{d.name}</span>
            </Link>
          ))}
        </div>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New database"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <Input autoFocus placeholder="Database name" value={name} onChange={(e) => setName(e.target.value)} />
      </Dialog>
    </div>
  );
}
