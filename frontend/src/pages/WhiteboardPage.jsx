import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Hand, MousePointer, Pen, Square, Type, Undo2 } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { IconButton } from "../components/ui.jsx";
import "./whiteboard.css";

const TOOLS = [
  { id: "select", label: "Select", icon: MousePointer },
  { id: "hand", label: "Pan", icon: Hand },
  { id: "pen", label: "Pen", icon: Pen },
  { id: "rect", label: "Rectangle", icon: Square },
  { id: "arrow", label: "Arrow", icon: ArrowRight },
  { id: "text", label: "Text", icon: Type },
];

export default function WhiteboardPage() {
  const { whiteboardId } = useParams();
  const svgRef = useRef(null);
  const [elements, setElements] = useState([]);
  const [tool, setTool] = useState("pen");
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [drawing, setDrawing] = useState(null);
  const [pendingOps, setPendingOps] = useState([]);
  const dragRef = useRef(null);

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

  const commitElement = (el) => {
    setElements((prev) => [...prev, el]);
    const op = { op_type: "add", payload: el };
    persist([op]);
  };

  const onPointerDown = (e) => {
    const pt = toWorld(e.clientX, e.clientY);
    if (tool === "hand") {
      dragRef.current = { startX: e.clientX, startY: e.clientY, x: transform.x, y: transform.y };
      return;
    }
    if (tool === "pen") {
      const el = { id: genId(), type: "pen", points: [pt], stroke: "#A66BFF", width: 2 };
      setDrawing(el);
      return;
    }
    if (tool === "rect" || tool === "arrow" || tool === "text") {
      const el = { id: genId(), type: tool, x: pt.x, y: pt.y, w: 0, h: 0, stroke: "#A66BFF" };
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

  return (
    <div className="whiteboard">
      <div className="wb-toolbar">
        {TOOLS.map(({ id, label, icon }) => (
          <button
            key={id}
            className={`wb-tool ${tool === id ? "wb-tool-active" : ""}`}
            onClick={() => setTool(id)}
            title={label}
          >
            <icon.icon size={16} />
          </button>
        ))}
        <span className="wb-sep" />
        <IconButton icon={Undo2} label="Back" onClick={() => window.history.back()} />
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
            <ElementView key={el.id} el={el} />
          ))}
          {drawing && <ElementView el={drawing} />}
        </g>
      </svg>
    </div>
  );
}

function ElementView({ el }) {
  if (el.type === "pen") {
    const d = el.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
    return <path d={d} stroke={el.stroke} strokeWidth={el.width} fill="none" strokeLinecap="round" strokeLinejoin="round" />;
  }
  if (el.type === "rect") {
    return <rect x={el.x} y={el.y} width={el.w} height={el.h} stroke={el.stroke} fill="none" strokeWidth={2} />;
  }
  if (el.type === "arrow") {
    return (
      <g stroke={el.stroke} strokeWidth={2} fill="none">
        <line x1={el.x} y1={el.y} x2={el.x + el.w} y2={el.y + el.h} />
        <path d={`M${el.x + el.w} ${el.y + el.h} l-8 -4 M${el.x + el.w} ${el.y + el.h} l-4 -8`} />
      </g>
    );
  }
  if (el.type === "text") {
    return (
      <text x={el.x} y={el.y} fill={el.stroke} fontSize={16}>
        {el.text}
      </text>
    );
  }
  return null;
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}
