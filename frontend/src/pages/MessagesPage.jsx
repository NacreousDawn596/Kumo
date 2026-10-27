import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { Link2, MessageSquare, Send, X } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { useAuth } from "../store/auth.js";
import { Avatar, EmptyState } from "../components/ui.jsx";
import CallBar from "../components/CallBar.jsx";
import MessagePreview from "../components/MessagePreview.jsx";
import { connectRealtime, onEvent, subscribeRoom } from "../lib/realtime.js";
import "../styles/pages.css";
import "./messages.css";

export default function MessagesPage() {
  const { conversationId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [link, setLink] = useState(null);
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
    mutationFn: ({ body, link }) =>
      apiPost(`/api/conversations/${conversationId}/messages`, {
        body,
        link_resource_type: link?.type || null,
        link_resource_id: link?.id || null,
      }),
    onSuccess: () => {
      setDraft("");
      setLink(null);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const react = useMutation({
    mutationFn: ({ id, emoji }) => apiPost(`/api/messages/${id}/reactions`, { emoji }),
    onSuccess: () => refetch(),
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
            <div className="messages-thread-head">
              <span>{current?.title || "Conversation"}</span>
              {conversationId && (
                <CallBar conversationId={conversationId} otherName={current?.title} />
              )}
            </div>
            <div className="messages-scroll" ref={scrollRef}>
              {messages.map((m) => (
                <MessageItem key={m.id} m={m} own={m.sender_id === user.id} onReact={(emoji) => react.mutate({ id: m.id, emoji })} />
              ))}
            </div>
            <form
              className="messages-composer"
              onSubmit={(e) => {
                e.preventDefault();
                if (draft.trim()) send.mutate({ body: draft.trim(), link });
              }}
            >
              <input
                className="messages-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type a message…"
              />
              <LinkPicker link={link} setLink={setLink} />
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

const EMOJIS = ["👍", "❤️", "😂", "🎉", "🔥", "👏"];

function MessageItem({ m, own, onReact }) {
  const [picker, setPicker] = useState(false);

  const grouped = (m.reactions || []).reduce((acc, r) => {
    acc[r.emoji] = (acc[r.emoji] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className={`msg ${own ? "msg-own" : ""}`}>
      {!own && <Avatar name={m.sender_id} size={26} />}
      <div className="msg-col">
        <div className="msg-bubble">{m.body}</div>
        {m.link_resource_type && m.link_resource_id && (
          <MessagePreview type={m.link_resource_type} id={m.link_resource_id} />
        )}
        {Object.keys(grouped).length > 0 && (
          <div className="msg-reactions">
            {Object.entries(grouped).map(([emoji, count]) => (
              <button key={emoji} className="msg-reaction" onClick={() => onReact(emoji)}>
                {emoji} {count > 1 ? count : ""}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="msg-meta">
        <span className="msg-time">{format(new Date(m.created_at), "h:mm a")}</span>
        <span className="msg-react-btn" onClick={() => setPicker((p) => !p)} title="Add reaction">+</span>
        {picker && (
          <span className="msg-emoji-picker">
            {EMOJIS.map((e) => (
              <button key={e} onClick={() => { onReact(e); setPicker(false); }}>{e}</button>
            ))}
          </span>
        )}
      </div>
    </div>
  );
}

function LinkPicker({ link, setLink }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  const search = async (val) => {
    setQ(val);
    if (val.length < 2) return setResults([]);
    setResults(await api(`/api/knowledge/search?q=${encodeURIComponent(val)}`));
  };

  return (
    <div className="link-picker">
      {link ? (
        <span className="link-chip">
          {link.title} <button onClick={() => setLink(null)}><X size={12} /></button>
        </span>
      ) : (
        <button type="button" className="messages-link-btn" title="Attach a link" onClick={() => setOpen((o) => !o)}>
          <Link2 size={16} />
        </button>
      )}
      {open && (
        <div className="link-search-pop">
          <input autoFocus placeholder="Search pages, files, tasks…" value={q} onChange={(e) => search(e.target.value)} />
          <div className="transfer-results">
            {results.slice(0, 8).map((r) => (
              <button key={`${r.type}-${r.id}`} className="transfer-result" onClick={() => { setLink(r); setOpen(false); }}>
                <span>{r.title}</span>
                <span className="transfer-result-user">{r.type}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
