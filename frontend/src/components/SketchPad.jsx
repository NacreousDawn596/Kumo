import { useRef, useState } from "react";
import { Eraser, Pencil } from "lucide-react";
import { apiPost } from "../api/client.js";

const ELEMENTS = ["C", "N", "O", "S", "P", "F", "Cl", "H"];
const GRID = 40;
const HIT_RADIUS = 16;
const SCALE = 0.0375; // 40 px -> 1.5 Angstrom

function buildMolfile(atoms, bonds) {
  const lines = [];
  lines.push("Sketch");
  lines.push("  Kumo sketcher");
  lines.push("");
  lines.push(`${String(atoms.length).padStart(3)}${String(bonds.length).padStart(3)}${"  0".repeat(8)}999 V2000`);
  for (const a of atoms) {
    const x = (a.x * SCALE).toFixed(4).padStart(10);
    const y = (a.y * SCALE).toFixed(4).padStart(10);
    lines.push(`${x}${y}    0.0000 ${a.symbol.padEnd(3)} 0${"  0".repeat(11)}`);
  }
  for (const b of bonds) {
    lines.push(`${String(b.a + 1).padStart(3)}${String(b.b + 1).padStart(3)}${String(b.order).padStart(3)}  0`);
  }
  lines.push("M  END");
  return lines.join("\n");
}

export default function SketchPad({ onStructure }) {
  const svgRef = useRef(null);
  const [atoms, setAtoms] = useState([]);
  const [bonds, setBonds] = useState([]);
  const [element, setElement] = useState("C");
  const [bondOrder, setBondOrder] = useState(1);
  const [dragFrom, setDragFrom] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const nextId = () => Math.random().toString(36).slice(2);

  const point = (e) => {
    const rect = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const snap = (p) => ({ x: Math.round(p.x / GRID) * GRID, y: Math.round(p.y / GRID) * GRID });

  const hitAtom = (p) => {
    let best = null;
    let bestDist = HIT_RADIUS;
    for (const a of atoms) {
      const d = Math.hypot(a.x - p.x, a.y - p.y);
      if (d <= bestDist) { best = a; bestDist = d; }
    }
    return best;
  };

  const bondBetween = (aId, bId) => bonds.find((b) => (b.a === aId && b.b === bId) || (b.a === bId && b.b === aId));

  const addOrCycleBond = (aId, bId) => {
    if (aId === bId) return;
    const existing = bondBetween(aId, bId);
    if (existing) {
      setBonds((bs) => existing.order >= 3 ? bs.filter((b) => b !== existing) : bs.map((b) => b === existing ? { ...b, order: b.order + 1 } : b));
    } else {
      setBonds((bs) => [...bs, { a: aId, b: bId, order: bondOrder }]);
    }
  };

  const onDown = (e) => {
    e.preventDefault();
    svgRef.current.setPointerCapture(e.pointerId);
    const p = snap(point(e));
    const hit = hitAtom(p);
    if (hit) {
      setDragFrom(hit.id);
      setSelected(hit.id);
    } else {
      const id = nextId();
      setAtoms((as) => [...as, { id, symbol: element, x: p.x, y: p.y }]);
      setDragFrom(id);
      setSelected(id);
    }
  };

  const onMove = (e) => {
    if (!dragFrom) return;
    setCursor(point(e));
  };

  const onUp = (e) => {
    if (dragFrom) {
      const target = hitAtom(point(e));
      if (target && target.id !== dragFrom) addOrCycleBond(dragFrom, target.id);
    }
    setDragFrom(null);
    setCursor(null);
  };

  const onKeyDown = (e) => {
    if ((e.key === "Delete" || e.key === "Backspace") && selected) {
      setAtoms((as) => as.filter((a) => a.id !== selected));
      setBonds((bs) => bs.filter((b) => b.a !== selected && b.b !== selected));
      setSelected(null);
    }
  };

  const clear = () => { setAtoms([]); setBonds([]); setSelected(null); setError(""); };

  const generate = async () => {
    setError("");
    if (atoms.length === 0) { setError("Draw at least one atom first."); return; }
    setPending(true);
    try {
      const res = await apiPost("/api/chemistry/sketch", { molfile: buildMolfile(atoms, bonds) });
      if (res.valid) onStructure(res);
      else setError(res.error || "Invalid structure.");
    } catch {
      setError("Failed to generate the structure.");
    } finally {
      setPending(false);
    }
  };

  const previewAtom = dragFrom ? atoms.find((a) => a.id === dragFrom) : null;

  return (
    <div className="sketch">
      <div className="sketch-palette">
        <span className="sketch-label">Atom</span>
        {ELEMENTS.map((el) => (
          <button key={el} className={`sketch-el ${element === el ? "sketch-el-active" : ""}`} onClick={() => setElement(el)}>
            {el}
          </button>
        ))}
        <span className="sketch-label">Bond</span>
        {[1, 2, 3].map((o) => (
          <button key={o} className={`sketch-el ${bondOrder === o ? "sketch-el-active" : ""}`} onClick={() => setBondOrder(o)}>
            {o}
          </button>
        ))}
        <span className="sketch-actions">
          <button className="btn btn-ghost btn-sm" onClick={clear} title="Clear"><Eraser size={14} /> Clear</button>
          <button className="btn btn-primary btn-sm" onClick={generate} disabled={pending} title="Generate 3D">
            <Pencil size={14} /> {pending ? "Building…" : "Generate 3D"}
          </button>
        </span>
      </div>

      <svg
        ref={svgRef}
        className="sketch-canvas"
        tabIndex={0}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onKeyDown={onKeyDown}
        onPointerCancel={() => { setDragFrom(null); setCursor(null); }}
      >
        {bonds.map((b, i) => {
          const A = atoms.find((a) => a.id === b.a);
          const B = atoms.find((a) => a.id === b.b);
          if (!A || !B) return null;
          return <BondLine key={i} x1={A.x} y1={A.y} x2={B.x} y2={B.y} order={b.order} />;
        })}
        {dragFrom && cursor && previewAtom && (
          <line x1={previewAtom.x} y1={previewAtom.y} x2={cursor.x} y2={cursor.y} stroke="var(--accent)" strokeWidth={2} strokeDasharray="4 3" />
        )}
        {atoms.map((a) => (
          <g key={a.id} transform={`translate(${a.x} ${a.y})`}>
            <circle r={15} className={`sketch-atom ${selected === a.id ? "sketch-atom-selected" : ""}`} />
            <text y={4} textAnchor="middle" className="sketch-atom-label">{a.symbol}</text>
          </g>
        ))}
      </svg>

      <p className="chem-hint">Click empty space to add an atom · drag atom-to-atom to draw a bond (repeat to cycle single→double→triple) · Delete to remove.</p>
      {error && <p className="auth-error">{error}</p>}
    </div>
  );
}

function BondLine({ x1, y1, x2, y2, order }) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const nx = (-dy / len) * 4;
  const ny = (dx / len) * 4;
  if (order === 2) {
    return (
      <g stroke="var(--text-secondary)" strokeWidth={2}>
        <line x1={x1 + nx} y1={y1 + ny} x2={x2 + nx} y2={y2 + ny} />
        <line x1={x1 - nx} y1={y1 - ny} x2={x2 - nx} y2={y2 - ny} />
      </g>
    );
  }
  if (order === 3) {
    return (
      <g stroke="var(--text-secondary)" strokeWidth={2}>
        <line x1={x1} y1={y1} x2={x2} y2={y2} />
        <line x1={x1 + nx * 2} y1={y1 + ny * 2} x2={x2 + nx * 2} y2={y2 + ny * 2} />
        <line x1={x1 - nx * 2} y1={y1 - ny * 2} x2={x2 - nx * 2} y2={y2 - ny * 2} />
      </g>
    );
  }
  return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--text-secondary)" strokeWidth={2} />;
}
