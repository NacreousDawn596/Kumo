import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { File, FileText, Folder, Image, Link2, MoreHorizontal, Share, Trash2, Upload, UserPlus, X } from "lucide-react";
import { api, apiPost, apiUpload } from "../api/client.js";
import { Button, Dialog, EmptyState, Input, Menu } from "../components/ui.jsx";
import StorageMeter, { formatBytes } from "../components/StorageMeter.jsx";
import "../styles/pages.css";
import "./vault.css";

function iconFor(mime) {
  if (mime === "application/pdf") return FileText;
  if (mime?.startsWith("image/")) return Image;
  return File;
}

export default function VaultPage() {
  const queryClient = useQueryClient();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [transferFile, setTransferFile] = useState(null);
  const [transferQuery, setTransferQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);

  const { data: files = [] } = useQuery({
    queryKey: ["files"],
    queryFn: () => api("/api/vault/files"),
  });

  const upload = useMutation({
    mutationFn: (file) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("name", file.name);
      return apiUpload("/api/vault/files", fd);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["files"] }),
  });

  const transfer = useMutation({
    mutationFn: ({ fileId, targetId }) => apiPost(`/api/vault/files/${fileId}/transfer`, { target_user_id: targetId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["storage"] });
      setTransferFile(null);
      setTransferQuery("");
      setSearchResults([]);
    },
  });

  const unlink = useMutation({
    mutationFn: (fileId) => apiPost(`/api/vault/files/${fileId}/unlink`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["storage"] });
    },
  });

  const remove = useMutation({
    mutationFn: (fileId) => api(`/api/vault/files/${fileId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["storage"] });
    },
  });

  const onPick = async (e) => {
    const selected = [...e.target.files];
    e.target.value = "";
    if (selected.length === 0) return;
    setUploading(true);
    try {
      for (const f of selected) await upload.mutateAsync(f);
    } finally {
      setUploading(false);
    }
  };

  const searchUsers = async (q) => {
    setTransferQuery(q);
    if (q.length < 1) {
      setSearchResults([]);
      return;
    }
    const res = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
    setSearchResults(res);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Vault</h1>
          <p className="page-subtitle">{files.length} file{files.length === 1 ? "" : "s"}</p>
        </div>
        <Button variant="primary" icon={Upload} loading={uploading} onClick={() => inputRef.current?.click()}>
          Upload
        </Button>
        <input ref={inputRef} type="file" multiple hidden onChange={onPick} />
      </div>

      <StorageMeter />

      {files.length === 0 ? (
        <EmptyState
          icon={Folder}
          title="Your vault is empty"
          description="Upload PDFs, images, and documents to study and share."
          action={<Button variant="primary" icon={Upload} onClick={() => inputRef.current?.click()}>Upload a file</Button>}
        />
      ) : (
        <div className="vault-grid" style={{ marginTop: 16 }}>
          {files.map((f) => {
            const Icon = iconFor(f.mime_type);
            return (
              <div key={f.id} className="file-card">
                <div className="file-card-top">
                  <Link to={f.previewable ? `/documents/${f.id}` : "/vault"} className="file-card-icon">
                    <Icon size={18} strokeWidth={1.8} />
                  </Link>
                  <Menu
                    align="right"
                    trigger={<button className="file-card-menu" aria-label="File actions"><MoreHorizontal size={16} /></button>}
                    items={[
                      f.previewable && { label: "Open", onClick: () => (window.location.href = `/documents/${f.id}`) },
                      { label: "Download", icon: Share, onClick: () => (window.location.href = `/api/vault/files/${f.id}/content`) },
                      { divider: true },
                      !f.is_linked && { label: "Transfer to…", icon: UserPlus, onClick: () => setTransferFile(f) },
                      f.is_linked && { label: "Remove link", icon: X, onClick: () => unlink.mutate(f.id) },
                      !f.is_linked && { label: "Delete", icon: Trash2, danger: true, onClick: () => remove.mutate(f.id) },
                    ].filter(Boolean)}
                  />
                </div>
                <span className="file-card-name">{f.name}</span>
                <span className="file-card-meta">
                  {formatBytes(f.size_bytes)} · {format(new Date(f.updated_at), "MMM d")}
                  {f.is_linked && <span className="file-card-link"><Link2 size={11} /> linked</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <Dialog
        open={!!transferFile}
        onClose={() => setTransferFile(null)}
        title={`Transfer “${transferFile?.name || ""}”`}
        footer={
          <Button variant="ghost" onClick={() => setTransferFile(null)}>Cancel</Button>
        }
      >
        <p className="transfer-note">
          Ownership moves to another student. Edits, comments, versions, and annotations
          are all preserved — only the owner changes.
        </p>
        <Input
          autoFocus
          placeholder="Search by username or name…"
          value={transferQuery}
          onChange={(e) => searchUsers(e.target.value)}
        />
        <div className="transfer-results">
          {searchResults.map((u) => (
            <button
              key={u.id}
              className="transfer-result"
              disabled={transfer.isPending}
              onClick={() => transfer.mutate({ fileId: transferFile.id, targetId: u.id })}
            >
              <span>{u.display_name}</span>
              <span className="transfer-result-user">@{u.username}</span>
            </button>
          ))}
        </div>
        {transfer.error && <p className="auth-error">{transfer.error.message}</p>}
      </Dialog>
    </div>
  );
}
