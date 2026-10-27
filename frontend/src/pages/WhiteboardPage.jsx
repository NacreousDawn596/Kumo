import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Eraser,
  Hand,
  MousePointer,
  Pen,
  Redo2,
  Square,
  Type,
  Undo2,
} from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { IconButton } from "../components/ui.jsx";
import "./whiteboard.css";

const STROKE = "#7c2bb4";

const TOOLS = [
  { id: "select", label: "Select (V)", icon: MousePointer },
  { id: "hand", label: "Pan (H)", icon: Hand },
  { id: "pen", label: "Pen (P)", icon: Pen },
  { id: "erase", label: "Eraser (E)", icon: Eraser },
  { id: "rect", label: "Rectangle (R)", icon: Square },
  { id: "arrow", label: "Arrow (A)", icon: ArrowRight },
  { id: "text", label: "Text (T)", icon: Type },
];

export default function WhiteboardPage() {
  const { whiteboardId } = useParams();
  const navigate = useNavigate();
  const svgRef = useRef(null);
  const [elements, setElements] = useState([]);
  const [tool, setTool] = useState("select");
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [drawing, setDrawing] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const dragRef = useRef(null);
  const undoStack = useRef([]);
  const redoStack = useRef([]);
  const [, forceRender] = useState(0);

  const { data: wb } = useQuery({
    queryKey: ["whiteboard", whiteboardId],
    queryFn: () => api(`/api/whiteboards/${whiteboardId}`),
  });

  const initializedFor = useRef(null);
  useEffect(() => {
    if (wb && initializedFor.current !== whiteboardId) {
      setElements(wb.elements || []);
      initializedFor.current = whiteboardId;
    }
  }, [wb, whiteboardId]);

  const toWorld = (clientX, clientY) => {
    const rect = svgRef.current.getBoundingClientRect();
    return {
      x: (clientX - rect.left - transform.x) / transform.k,
      y: (clientY - rect.top - transform.y) / transform.k,
    };
  };

  const persist = (ops) => {
    apiPost(`/api/whiteboards/${whiteboardId}/operations`, ops).catch(() => {});
  };

  // Apply a change to local state and persist it (no history bookkeeping).
  const applyOp = (opType, payload) => {
    if (opType === "add") {
      setElements((prev) => [...prev, payload]);
    } else if (opType === "remove") {
      setElements((prev) => prev.filter((e) => e.id !== payload.id));
    }
    persist([{ op_type: opType, payload }]);
  };

  // Commit a forward operation and record it for undo.
  const commit = (opType, payload) => {
    if (opType === "add") {
      applyOp("add", payload);
      undoStack.current.push({ opType: "add", payload });
    } else if (opType === "remove") {
      const removed = elements.find((e) => e.id === payload.id);
      applyOp("remove", payload);
      if (removed) undoStack.current.push({ opType: "remove", payload: removed });
    }
    redoStack.current = [];
    forceRender((n) => n + 1);
  };

  const commitElement = (el) => commit("add", el);

  const undo = () => {
    const action = undoStack.current.pop();
    if (!action) return;
    if (action.opType === "add") {
      applyOp("remove", { id: action.payload.id });
    } else {
      applyOp("add", action.payload);
    }
    redoStack.current.push(action);
    forceRender((n) => n + 1);
  };

  const redo = () => {
    const action = redoStack.current.pop();
    if (!action) return;
    if (action.opType === "add") {
      applyOp("add", action.payload);
    } else {
      applyOp("remove", { id: action.payload.id });
    }
    undoStack.current.push(action);
    forceRender((n) => n + 1);
  };

  // Keyboard shortcuts: tool keys, undo/redo, delete, escape.
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedId) {
          commit("remove", { id: selectedId });
          setSelectedId(null);
        }
        return;
      }
      if (e.key === "Escape") {
        setSelectedId(null);
        return;
      }

      const keyMap = { v: "select", h: "hand", p: "pen", e: "erase", r: "rect", a: "arrow", t: "text" };
      const mapped = keyMap[e.key.toLowerCase()];
      if (mapped && !e.metaKey && !e.ctrlKey) setTool(mapped);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, elements, redo, undo]);

  const hitTest = (pt) => {
    // Topmost element first.
    for (let i = elements.length - 1; i >= 0; i--) {
      const el = elements[i];
      const pad = 6 / transform.k;
      if (el.type === "pen" && el.points) {
        for (const p of el.points) {
          if (Math.hypot(p.x - pt.x, p.y - pt.y) < pad) return el;
        }
      } else if (el.type === "rect") {
        const x = Math.min(el.x, el.x + el.w);
        const y = Math.min(el.y, el.y + el.h);
        const w = Math.abs(el.w);
        const h = Math.abs(el.h);
        if (pt.x >= x - pad && pt.x <= x + w + pad && pt.y >= y - pad && pt.y <= y + h + pad) return el;
      } else if (el.type === "arrow") {
        const x2 = el.x + el.w;
        const y2 = el.y + el.h;
        if (distToSegment(pt, el.x, el.y, x2, y2) < pad) return el;
      } else if (el.type === "text") {
        if (Math.hypot(pt.x - el.x, pt.y - el.y) < 16 / transform.k) return el;
      }
    }
    return null;
  };

  const onPointerDown = (e) => {
    const pt = toWorld(e.clientX, e.clientY);

    if (tool === "hand") {
      dragRef.current = { startX: e.clientX, startY: e.clientY, x: transform.x, y: transform.y };
      return;
    }
    if (tool === "erase") {
      const hit = hitTest(pt);
      if (hit) commit("remove", { id: hit.id });
      return;
    }
    if (tool === "select") {
      const hit = hitTest(pt);
      setSelectedId(hit ? hit.id : null);
      return;
    }
    if (tool === "pen") {
      const el = { id: genId(), type: "pen", points: [pt], stroke: STROKE, width: 2.5 };
      setDrawing(el);
      return;
    }
    if (tool === "rect" || tool === "arrow" || tool === "text") {
      const el = { id: genId(), type: tool, x: pt.x, y: pt.y, w: 0, h: 0, stroke: STROKE };
      setDrawing(el);
      return;
    }
  };

  const onPointerMove = (e) => {
    if (dragRef.current) {
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      setTransform((t) => ({ ...t, x: dragRef.current.x + dx, y: dragRef.current.y + dy }));
      return;
    }
    if (!drawing) return;
    const pt = toWorld(e.clientX, e.clientY);
    if (drawing.type === "pen") {
      setDrawing((d) => ({ ...d, points: [...d.points, pt] }));
    } else {
      setDrawing((d) => ({ ...d, w: pt.x - d.x, h: pt.y - d.y }));
    }
  };

  const onPointerUp = () => {
    dragRef.current = null;
    if (drawing) {
      if (drawing.type === "pen" && drawing.points.length > 1) {
        commitElement(drawing);
      } else if (drawing.type === "rect" || drawing.type === "arrow") {
        if (Math.abs(drawing.w) > 3 || Math.abs(drawing.h) > 3) commitElement(drawing);
      } else if (drawing.type === "text") {
        const text = window.prompt("Label:");
        if (text) commitElement({ ...drawing, text });
      }
      setDrawing(null);
    }
  };

  const onWheel = (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setTransform((t) => ({ ...t, k: Math.max(0.1, Math.min(6, t.k * factor)) }));
  };

  const canUndo = undoStack.current.length > 0;
  const canRedo = redoStack.current.length > 0;

  return (
    <div className="whiteboard">
      <div className="wb-toolbar">
        <IconButton icon={ArrowLeft} label="Back" onClick={() => navigate(-1)} />

        <span className="wb-sep" />

        {TOOLS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`wb-tool ${tool === id ? "wb-tool-active" : ""}`}
            onClick={() => setTool(id)}
            title={label}
          >
            <Icon size={16} />
          </button>
        ))}

        <span className="wb-sep" />

        <button className="wb-tool" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
          <Undo2 size={16} />
        </button>
        <button className="wb-tool" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Y)">
          <Redo2 size={16} />
        </button>

        <span className="wb-name">{wb?.name}</span>
      </div>

      <svg
        ref={svgRef}
        className="wb-canvas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onWheel={onWheel}
        style={{ touchAction: "none" }}
      >
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
          {elements.map((el) => (
            <ElementView key={el.id} el={el} selected={el.id === selectedId} />
          ))}
          {drawing && <ElementView el={drawing} />}
        </g>
      </svg>
    </div>
  );
}

function ElementView({ el, selected }) {
  const common = selected
    ? { filter: "drop-shadow(0 0 0 1px var(--focus-ring))" }
    : {};
  if (el.type === "pen") {
    const d = el.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
    return (
      <path
        d={d}
        stroke={el.stroke}
        strokeWidth={el.width}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        {...common}
      />
    );
  }
  if (el.type === "rect") {
    return (
      <rect
        x={Math.min(el.x, el.x + el.w)}
        y={Math.min(el.y, el.y + el.h)}
        width={Math.abs(el.w)}
        height={Math.abs(el.h)}
        stroke={el.stroke}
        fill="none"
        strokeWidth={2}
        {...common}
      />
    );
  }
  if (el.type === "arrow") {
    return (
      <g stroke={el.stroke} strokeWidth={2} fill="none" {...common}>
        <line x1={el.x} y1={el.y} x2={el.x + el.w} y2={el.y + el.h} />
        <path d={`M${el.x + el.w} ${el.y + el.h} l-8 -4 M${el.x + el.w} ${el.y + el.h} l-4 -8`} />
      </g>
    );
  }
  if (el.type === "text") {
    return (
      <text x={el.x} y={el.y} fill={el.stroke} fontSize={16} {...common}>
        {el.text}
      </text>
    );
  }
  return null;
}

function distToSegment(p, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  let t = lenSq === 0 ? 0 : ((p.x - x1) * dx + (p.y - y1) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (x1 + t * dx), p.y - (y1 + t * dy));
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}
