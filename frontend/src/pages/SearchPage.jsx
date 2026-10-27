import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileText, Folder, ListTodo, Search, UserRound, Users } from "lucide-react";
import { api } from "../api/client.js";
import { Input } from "../components/ui.jsx";
import "../styles/pages.css";

const TYPE_ICON = {
  page: FileText,
  file: Folder,
  task: ListTodo,
  group: Users,
  user: UserRound,
};

function resultPath(r) {
  switch (r.type) {
    case "page":
      return `/pages/${r.id}`;
    case "task":
      return "/tasks";
    case "group":
      return `/groups/${r.id}`;
    case "user":
      return "/messages";
    default:
      return "/vault";
  }
}

export default function SearchPage() {
  const [query, setQuery] = useState("");

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["search", query],
    queryFn: () => api(`/api/knowledge/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
  });

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Search</h1>
        </div>
      </div>

      <Input
        autoFocus
        placeholder="Search everything…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {query.length >= 2 && (
        <div className="search-results" style={{ marginTop: 16 }}>
          {isFetching ? null : results.length === 0 ? (
            <p className="home-muted">No results for “{query}”.</p>
          ) : (
            results.map((r) => {
              const Icon = TYPE_ICON[r.type] || Search;
              return (
                <Link key={`${r.type}-${r.id}`} to={resultPath(r)} className="search-result">
                  <Icon size={15} className="home-row-icon" />
                  <span className="search-result-title">{r.title}</span>
                  <span className="search-result-type">{r.type}</span>
                </Link>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
