import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, FileText, ListTodo } from "lucide-react";
import { Dialog, Button, Input, Textarea } from "./ui.jsx";
import { api, apiPost } from "../api/client.js";

const KINDS = [
  { id: "note", label: "Note", icon: FileText },
  { id: "task", label: "Task", icon: ListTodo },
  { id: "event", label: "Event", icon: CalendarPlus },
];

export default function QuickCapture({ open, onClose }) {
  const [kind, setKind] = useState("note");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: async () => {
      if (kind === "note") {
        const page = await apiPost("/api/pages", { title: title || "Untitled" });
        if (body) {
          await api(`/api/pages/${page.id}/blocks`, {
            method: "PUT",
            body: [{ block_type: "paragraph", content: body }],
          });
        }
        return { path: `/pages/${page.id}` };
      }
      if (kind === "task") {
        await apiPost("/api/tasks", { title: title || "Untitled task", description: body });
        return { path: "/tasks" };
      }
      if (kind === "event") {
        await apiPost("/api/calendar", {
          title: title || "Untitled event",
          description: body,
          start_at: new Date().toISOString(),
          all_day: true,
        });
        return { path: "/calendar" };
      }
      return { path: "/" };
    },
    onSuccess: ({ path }) => {
      queryClient.invalidateQueries();
      onClose();
      setTitle("");
      setBody("");
      navigate(path);
    },
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Quick capture"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            onClick={() => create.mutate()}
          >
            Create
          </Button>
        </>
      }
    >
      <div className="qc-kinds">
        {KINDS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`qc-kind ${kind === id ? "qc-kind-active" : ""}`}
            onClick={() => setKind(id)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
      <div className="qc-fields">
        <Input
          autoFocus
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create.mutate()}
        />
        <Textarea
          placeholder={kind === "task" ? "Details" : "Write something…"}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
        />
      </div>
    </Dialog>
  );
}
