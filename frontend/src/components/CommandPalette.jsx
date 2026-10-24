import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Folder,
  ListTodo,
  Plus,
  Search,
  Users,
  Video,
  CalendarPlus,
  Network,
} from "lucide-react";
import { useCommandPalette } from "../store/commandPalette.js";
import { api } from "../api/client.js";
import "./commandPalette.css";

const TYPE_ICON = {
  page: FileText,
  file: Folder,
  task: ListTodo,
  group: Users,
};

const ACTIONS = [
  { label: "Create a note", to: "/notes", icon: FileText },
  { label: "Create a task", to: "/tasks", icon: ListTodo },
  { label: "Create a calendar event", to: "/calendar", icon: CalendarPlus },
  { label: "Start a study session", to: "/sessions", icon: Video },
  { label: "Open the knowledge graph", to: "/knowledge", icon: Network },
  { label: "Go to settings", to: "/settings", icon: Search },
];

export default function CommandPalette() {
  const { open, closePalette } = useCommandPalette();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const { data: results = [] } = useQuery({
    queryKey: ["search", query],
    queryFn: () => (query.length >= 2 ? api(`/api/knowledge/search?q=${encodeURIComponent(query)}`) : []),
    enabled: open && query.length >= 2,
  });

  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => setIndex(0), [query]);

  if (!open) return null;

  const items = query.length >= 2 ? results : ACTIONS;

  const onPick = (item) => {
    if (item.to) navigate(item.to);
    else if (item.type) navigate(resolvePath(item));
    closePalette();
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && items[index]) {
      e.preventDefault();
      onPick(items[index]);
    } else if (e.key === "Escape") {
      closePalette();
    }
  };

  return createPortal(
    <div className="palette-overlay" onMouseDown={closePalette}>
      <div className="palette" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <Search size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Search notes, files, tasks, groups…"
          />
        </div>
        <div className="palette-list">
          {items.length === 0 && query.length >= 2 && (
            <div className="palette-empty">No results for “{query}”</div>
          )}
          {items.map((item, i) => {
            const Icon = item.icon || TYPE_ICON[item.type] || FileText;
            return (
              <button
                key={item.id || item.label}
                className={`palette-item ${i === index ? "palette-item-active" : ""}`}
                onMouseEnter={() => setIndex(i)}
                onClick={() => onPick(item)}
              >
                <Icon size={15} strokeWidth={1.8} />
                <span className="palette-item-label">{item.title || item.label}</span>
                {item.type && <span className="palette-item-type">{item.type}</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>,
    document.body
  );
}

function resolvePath(item) {
  switch (item.type) {
    case "page":
      return `/pages/${item.id}`;
    case "file":
      return `/vault`;
    case "task":
      return `/tasks`;
    case "group":
      return `/groups/${item.id}`;
    default:
      return "/";
  }
}
