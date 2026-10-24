import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Bell, CheckCheck } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, EmptyState } from "../components/ui.jsx";
import "../styles/pages.css";

export default function InboxPage() {
  const queryClient = useQueryClient();
  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api("/api/notifications"),
  });

  const markAll = useMutation({
    mutationFn: () => apiPost("/api/notifications/read-all"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = notifications.filter((n) => !n.read_at).length;

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <div>
          <h1 className="page-title">Inbox</h1>
          <p className="page-subtitle">{unread} unread</p>
        </div>
        {unread > 0 && (
          <Button variant="secondary" icon={CheckCheck} onClick={() => markAll.mutate()}>
            Mark all read
          </Button>
        )}
      </div>

      {notifications.length === 0 ? (
        <EmptyState icon={Bell} title="You're all caught up" description="Notifications will appear here." />
      ) : (
        <div className="card">
          {notifications.map((n) => (
            <div key={n.id} className={`notif-row ${!n.read_at ? "notif-unread" : ""}`}>
              <div className="notif-main">
                <div className="notif-title">{n.title}</div>
                {n.body && <div className="notif-body">{n.body}</div>}
                <div className="notif-time">{formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
