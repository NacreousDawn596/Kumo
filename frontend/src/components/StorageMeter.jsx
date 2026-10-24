import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";

export function formatBytes(n) {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function StorageMeter() {
  const { data } = useQuery({
    queryKey: ["storage"],
    queryFn: () => api("/api/users/me/storage"),
  });

  if (!data) return null;
  const pct = data.quota_bytes > 0 ? Math.min(100, (data.used_bytes / data.quota_bytes) * 100) : 0;

  return (
    <div className="storage-meter">
      <div className="storage-bar">
        <div
          className="storage-bar-owned"
          style={{ width: `${(data.owned_bytes / data.quota_bytes) * 100}%` }}
        />
        <div
          className="storage-bar-linked"
          style={{ width: `${(data.linked_bytes / data.quota_bytes) * 100}%` }}
        />
      </div>
      <div className="storage-meta">
        <span>
          {formatBytes(data.used_bytes)} of {formatBytes(data.quota_bytes)} used ({pct.toFixed(0)}%)
        </span>
        <span className="storage-legend">
          <span className="storage-legend-owned" /> Owned {formatBytes(data.owned_bytes)}
          <span className="storage-legend-linked" /> Linked {formatBytes(data.linked_bytes)}
        </span>
      </div>
    </div>
  );
}
