import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { MessageSquare, Send } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { useAuth } from "../store/auth.js";
import { Avatar, EmptyState } from "../components/ui.jsx";
import { connectRealtime, onEvent, subscribeRoom } from "../lib/realtime.js";
import "../styles/pages.css";
import "./messages.css";

export default function MessagesPage() {
  const { conversationId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef(null);

  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api("/api/conversations"),
  });

  const { data: messages = [], refetch } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => api(`/api/conversations/${conversationId}/messages`),
    enabled: !!conversationId,
  });

  useEffect(() => {
    if (!conversationId) return;
    connectRealtime().then(() => subscribeRoom(`conversation:${conversationId}`));
    const off = onEvent((e) => {
      if (e.room === `conversation:${conversationId}` && e.type === "message") {
        refetch();
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
      }
    });
    return off;
  }, [conversationId, refetch, queryClient]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, conversationId]);

  const send = useMutation({
    mutationFn: (body) => apiPost(`/api/conversations/${conversationId}/messages`, { body }),
    onSuccess: () => {
      setDraft("");
      refetch();
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const current = conversations.find((c) => c.id === conversationId);

  return (
    <div className="messages-layout">
      <div className="messages-list">
        <div className="messages-list-head">Messages</div>
        {conversations.map((c) => (
          <button
            key={c.id}
            className={`message-conv ${c.id === conversationId ? "message-conv-active" : ""}`}
            onClick={() => navigate(`/messages/${c.id}`)}
          >
            <Avatar name={c.title || c.other_user_ids.join(", ")} size={34} />
            <div className="message-conv-main">
              <div className="message-conv-title">{c.title || c.other_user_ids.join(", ")}</div>
              {c.last_message && <div className="message-conv-preview">{c.last_message.body}</div>}
            </div>
            {c.unread_count > 0 && <span className="message-conv-unread">{c.unread_count}</span>}
          </button>
        ))}
      </div>

      <div className="messages-thread">
        {!conversationId ? (
          <EmptyState icon={MessageSquare} title="Select a conversation" description="Choose a conversation to start messaging." />
        ) : (
          <>
            <div className="messages-thread-head">{current?.title || "Conversation"}</div>
            <div className="messages-scroll" ref={scrollRef}>
              {messages.map((m) => (
                <div key={m.id} className={`msg ${m.sender_id === user.id ? "msg-own" : ""}`}>
                  {m.sender_id !== user.id && <Avatar name={m.sender_id} size={26} />}
                  <div className="msg-bubble">{m.body}</div>
                  <div className="msg-time">{format(new Date(m.created_at), "h:mm a")}</div>
                </div>
              ))}
            </div>
            <form
              className="messages-composer"
              onSubmit={(e) => {
                e.preventDefault();
                if (draft.trim()) send.mutate(draft.trim());
              }}
            >
              <input
                className="messages-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type a message…"
              />
              <button type="submit" className="messages-send" disabled={!draft.trim() || send.isPending}>
                <Send size={16} />
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
