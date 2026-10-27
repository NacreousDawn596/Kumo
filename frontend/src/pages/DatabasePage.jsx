import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { api, apiDelete, apiPatch, apiPost } from "../api/client.js";
import { Button, Dialog, Input } from "../components/ui.jsx";
import "../styles/pages.css";
import "./database.css";

const TYPES = [
  { id: "text", label: "Text" },
  { id: "number", label: "Number" },
  { id: "checkbox", label: "Checkbox" },
  { id: "select", label: "Select" },
  { id: "date", label: "Date" },
  { id: "url", label: "URL" },
];

export default function DatabasePage() {
  const { dbId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [addingProp, setAddingProp] = useState(false);
  const [propName, setPropName] = useState("");
  const [propType, setPropType] = useState("text");

  const { data: db } = useQuery({
    queryKey: ["database", dbId],
    queryFn: () => api(`/api/databases/${dbId}`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["database", dbId] });

  const addProperty = useMutation({
    mutationFn: () => apiPost(`/api/databases/${dbId}/properties`, { name: propName || "Property", prop_type: propType }),
    onSuccess: () => { invalidate(); setAddingProp(false); setPropName(""); },
  });

  const addRecord = useMutation({
    mutationFn: () => apiPost(`/api/databases/${dbId}/records`, { values: {} }),
    onSuccess: () => invalidate(),
  });

  const updateCell = useMutation({
    mutationFn: ({ recordId, propId, value }) =>
      apiPatch(`/api/databases/${dbId}/records/${recordId}`, { values: { [propId]: value } }),
    onSuccess: () => invalidate(),
  });

  const deleteRecord = useMutation({
    mutationFn: (recordId) => apiDelete(`/api/databases/${dbId}/records/${recordId}`),
    onSuccess: () => invalidate(),
  });

  const props = db?.properties || [];
  const records = db?.records || [];

  return (
    <div className="page db-page">
      <div className="editor-toolbar">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate("/databases")}>
          <ArrowLeft size={14} /> Databases
        </button>
      </div>

      <div className="page-header">
        <h1 className="page-title">{db?.name || "Database"}</h1>
        <div className="page-actions">
          <Button variant="secondary" icon={Plus} onClick={() => setAddingProp(true)}>Property</Button>
          <Button variant="primary" icon={Plus} onClick={() => addRecord.mutate()}>New row</Button>
        </div>
      </div>

      <div className="db-table">
        <table>
          <thead>
            <tr>
              {props.map((p) => (
                <th key={p.id}>
                  <span className="db-prop-name">{p.name}</span>
                  <span className="db-prop-type">{p.type}</span>
                </th>
              ))}
              <th className="db-row-actions" />
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id}>
                {props.map((p) => (
                  <td key={p.id}>
                    <Cell value={r.values?.[p.id]} type={p.type} onChange={(v) => updateCell.mutate({ recordId: r.id, propId: p.id, value: v })} />
                  </td>
                ))}
                <td className="db-row-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => deleteRecord.mutate(r.id)}>×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog
        open={addingProp}
        onClose={() => setAddingProp(false)}
        title="Add property"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddingProp(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => addProperty.mutate()}>Add</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Property name" value={propName} onChange={(e) => setPropName(e.target.value)} />
          <select className="input select" value={propType} onChange={(e) => setPropType(e.target.value)}>
            {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </div>
      </Dialog>
    </div>
  );
}

function Cell({ value, type, onChange }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  if (type === "checkbox") {
    return <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />;
  }

  if (editing) {
    return (
      <input
        className="db-cell-input"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => { onChange(draft); setEditing(false); }}
        onKeyDown={(e) => { if (e.key === "Enter") { onChange(draft); setEditing(false); } }}
      />
    );
  }

  return (
    <button
      className="db-cell"
      onClick={() => { setDraft(String(value ?? "")); setEditing(true); }}
    >
      {value == null || value === "" ? <span className="db-cell-empty">Empty</span> : String(value)}
    </button>
  );
}
