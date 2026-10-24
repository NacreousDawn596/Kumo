import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { ListTodo, Plus } from "lucide-react";
import { api, apiPatch, apiPost } from "../api/client.js";
import { Button, Dialog, EmptyState, Input, Select, Textarea } from "../components/ui.jsx";
import "../styles/pages.css";

const STATUSES = [
  { id: "todo", label: "To do" },
  { id: "in_progress", label: "In progress" },
  { id: "done", label: "Done" },
];

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("todo");
  const [priority, setPriority] = useState("none");
  const [dueDate, setDueDate] = useState("");
  const [description, setDescription] = useState("");

  const { data: tasks = [] } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api("/api/tasks"),
  });

  const create = useMutation({
    mutationFn: () =>
      apiPost("/api/tasks", {
        title,
        status,
        priority,
        description,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setCreating(false);
      setTitle("");
      setDescription("");
      setDueDate("");
    },
  });

  const toggle = useMutation({
    mutationFn: (task) => apiPatch(`/api/tasks/${task.id}`, { status: task.status === "done" ? "todo" : "done" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const grouped = {
    todo: tasks.filter((t) => t.status === "todo"),
    in_progress: tasks.filter((t) => t.status === "in_progress"),
    done: tasks.filter((t) => t.status === "done"),
  };

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Tasks</h1>
          <p className="page-subtitle">{tasks.filter((t) => t.status !== "done").length} open</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
          New task
        </Button>
      </div>

      {tasks.length === 0 ? (
        <EmptyState
          icon={ListTodo}
          title="No tasks yet"
          description="Track assignments and deadlines."
          action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Add a task</Button>}
        />
      ) : (
        STATUSES.map((s) =>
          grouped[s.id].length === 0 ? null : (
            <div className="section" key={s.id}>
              <h2 className="section-title">{s.label} · {grouped[s.id].length}</h2>
              <div className="card">
                {grouped[s.id].map((t) => (
                  <div key={t.id} className="card-row">
                    <input
                      type="checkbox"
                      className="task-check"
                      checked={t.status === "done"}
                      onChange={() => toggle.mutate(t)}
                    />
                    <span className={`task-title ${t.status === "done" ? "task-title-done" : ""}`}>
                      {t.title}
                    </span>
                    {t.priority !== "none" && <span className="task-priority">{t.priority}</span>}
                    {t.due_date && <span className="task-due">{format(new Date(t.due_date), "MMM d")}</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        )
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New task"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <div style={{ display: "flex", gap: 8 }}>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
            <Select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="none">No priority</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </Select>
            <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
