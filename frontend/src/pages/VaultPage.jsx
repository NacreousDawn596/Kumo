import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { File, FileText, Folder, Image, Upload } from "lucide-react";
import { api, apiUpload } from "../api/client.js";
import { Button, EmptyState } from "../components/ui.jsx";
import "../styles/pages.css";

function iconFor(mime) {
  if (mime === "application/pdf") return FileText;
  if (mime?.startsWith("image/")) return Image;
  return File;
}

export default function VaultPage() {
  const queryClient = useQueryClient();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

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

      {files.length === 0 ? (
        <EmptyState
          icon={Folder}
          title="Your vault is empty"
          description="Upload PDFs, images, and documents to study and share."
          action={<Button variant="primary" icon={Upload} onClick={() => inputRef.current?.click()}>Upload a file</Button>}
        />
      ) : (
        <div className="vault-grid">
          {files.map((f) => {
            const Icon = iconFor(f.mime_type);
            return (
              <Link
                key={f.id}
                to={f.previewable ? `/documents/${f.id}` : `/vault`}
                className="file-card"
              >
                <span className="file-card-icon">
                  <Icon size={18} strokeWidth={1.8} />
                </span>
                <span className="file-card-name">{f.name}</span>
                <span className="file-card-meta">
                  {format(new Date(f.updated_at), "MMM d")} · {(f.size_bytes / 1024).toFixed(0)} KB
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
