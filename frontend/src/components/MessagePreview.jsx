import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileText, ListTodo, File, Folder } from "lucide-react";
import { api } from "../api/client.js";

function pathFor(type, id) {
  switch (type) {
    case "page": return `/pages/${id}`;
    case "file": return `/vault`;
    case "task": return `/tasks`;
    default: return "/";
  }
}

export default function MessagePreview({ type, id }) {
  const { data } = useQuery({
    queryKey: ["preview", type, id],
    queryFn: async () => {
      try {
        if (type === "page") return { title: (await api(`/api/pages/${id}`)).title, icon: FileText };
        if (type === "file") return { title: (await api(`/api/vault/files/${id}`)).name, icon: Folder };
        if (type === "task") return { title: (await api(`/api/tasks/${id}`)).title, icon: ListTodo };
        return null;
      } catch {
        return null;
      }
    },
  });

  if (!data) return null;
  const Icon = data.icon || File;

  return (
    <Link to={pathFor(type, id)} className="msg-preview">
      <Icon size={16} />
      <span className="msg-preview-title">{data.title}</span>
      <span className="msg-preview-type">{type}</span>
    </Link>
  );
}
