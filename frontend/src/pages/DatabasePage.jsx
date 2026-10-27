import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, LayoutGrid, List, Plus, Table2 } from "lucide-react";
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

const VIEWS = [
  { id: "table", label: "Table", icon: Table2 },
  { id: "board", label: "Board", icon: LayoutGrid },
  { id: "gallery", label: "Gallery", icon: List },
];

export default function DatabasePage() {
  const { dbId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState("table");
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
    mutationFn: (values) => apiPost(`/api/databases/${dbId}/records`, { values: values || {} }),
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
  const titleProp = props.find((p) => p.type === "title") || props[0];
  const groupProp = props.find((p) => p.type === "select");

  const titleOf = (r) => (titleProp ? String(r.values?.[titleProp.id] ?? "") : "");

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
          <div className="view-switcher">
            {VIEWS.map((v) => (
              <button key={v.id} className={`view-chip ${view === v.id ? "view-chip-active" : ""}`} onClick={() => setView(v.id)} title={v.label}>
                <v.icon size={15} />
              </button>
            ))}
          </div>
          <Button variant="secondary" icon={Plus} onClick={() => setAddingProp(true)}>Property</Button>
          <Button variant="primary" icon={Plus} onClick={() => addRecord.mutate()}>New row</Button>
        </div>
      </div>

      {view === "table" && (
        <TableView props={props} records={records} updateCell={updateCell} deleteRecord={deleteRecord} />
      )}

      {view === "board" && (
        <BoardView props={props} records={records} groupProp={groupProp} titleOf={titleOf} updateCell={updateCell} addRecord={addRecord} deleteRecord={deleteRecord} />
      )}

      {view === "gallery" && (
        <GalleryView props={props} records={records} titleOf={titleOf} updateCell={updateCell} deleteRecord={deleteRecord} />
      )}

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

function TableView({ props, records, updateCell, deleteRecord }) {
  return (
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
  );
}

function BoardView({ records, groupProp, titleOf, updateCell, addRecord, deleteRecord }) {
  if (!groupProp) {
    return (
      <p className="home-muted">
        Add a <strong>Select</strong> property to use the board view — it groups records into columns.
      </p>
    );
  }
  const groups = {};
  for (const r of records) {
    const key = r.values?.[groupProp.id] || "No status";
    (groups[key] ||= []).push(r);
  }
  const columns = Object.keys(groups).length ? Object.keys(groups) : ["No status"];

  return (
    <div className="db-board">
      {columns.map((col) => (
        <div key={col} className="db-board-col">
          <div className="db-board-head">
            <span>{String(col)}</span>
            <span className="db-board-count">{groups[col]?.length || 0}</span>
          </div>
          <div className="db-board-cards">
            {(groups[col] || []).map((r) => (
              <div key={r.id} className="db-card">
                <div className="db-card-title">{titleOf(r) || "Untitled"}</div>
                <button className="btn btn-ghost btn-sm" onClick={() => deleteRecord.mutate(r.id)}>×</button>
              </div>
            ))}
          </div>
          <button className="db-board-add" onClick={() => addRecord.mutate({ [groupProp.id]: col === "No status" ? "" : col })}>+ New</button>
        </div>
      ))}
    </div>
  );
}

function GalleryView({ props, records, titleOf, updateCell, deleteRecord }) {
  const previewProps = props.filter((p) => p.type !== "title").slice(0, 3);
  return (
    <div className="db-gallery">
      {records.map((r) => (
        <div key={r.id} className="db-gallery-card">
          <div className="db-gallery-title">{titleOf(r) || "Untitled"}</div>
          {previewProps.map((p) => (
            <div key={p.id} className="db-gallery-prop">
              <span className="db-prop-type">{p.name}</span>
              <Cell value={r.values?.[p.id]} type={p.type} onChange={(v) => updateCell.mutate({ recordId: r.id, propId: p.id, value: v })} />
            </div>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={() => deleteRecord.mutate(r.id)}>Delete</button>
        </div>
      ))}
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
