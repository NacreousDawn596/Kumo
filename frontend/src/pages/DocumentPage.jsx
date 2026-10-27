import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Eraser,
  Highlighter,
  Pen,
  Redo2,
  Undo2,
} from "lucide-react";
import { api, apiDelete, apiGet, apiPost } from "../api/client.js";
import { Spinner } from "../components/ui.jsx";
import "./document.css";

const PEN_COLOR = "#7c2bb4";
const HIGHLIGHT_COLOR = "#e6c64a";

let pdfjsPromise = null;
async function loadPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = (async () => {
      const pdfjs = await import("pdfjs-dist");
      const worker = await import("pdfjs-dist/build/pdf.worker.min.mjs?url");
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      return pdfjs;
    })();
  }
  return pdfjsPromise;
}

export default function DocumentPage() {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const [pageNum, setPageNum] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [tool, setTool] = useState("pen");
  const [drawing, setDrawing] = useState(null);
  const undoStack = useRef([]);
  const redoStack = useRef([]);
  const [, forceRender] = useState(0);

  const { data: file } = useQuery({
    queryKey: ["file", fileId],
    queryFn: () => apiGet(`/api/vault/files/${fileId}`),
  });

  const { data: annotations = [] } = useQuery({
    queryKey: ["annotations", fileId],
    queryFn: () => apiGet(`/api/annotations/files/${fileId}`),
  });

  useEffect(() => {
    if (!file) return;
    if (file.mime_type !== "application/pdf") {
      setRendering(false);
      return;
    }
    let cancelled = false;
    let doc = null;

    (async () => {
      setRendering(true);
      const pdfjs = await loadPdfjs();
      const url = `/api/vault/files/${fileId}/preview`;
      const data = await fetch(url, { credentials: "include" });
      const buffer = await data.arrayBuffer();
      doc = await pdfjs.getDocument({ data: buffer }).promise;
      if (cancelled) return;
      setNumPages(doc.numPages);
      const page = await doc.getPage(pageNum);
      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;
      setRendering(false);
    })().catch(() => setRendering(false));

    return () => {
      cancelled = true;
      doc?.destroy();
    };
  }, [file, fileId, pageNum]);

  const toNormalized = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["annotations", fileId] });

  const createAnnotation = async (data) => {
    const created = await apiPost(`/api/annotations/files/${fileId}`, data);
    undoStack.current.push({ id: created.id, data });
    redoStack.current = [];
    forceRender((n) => n + 1);
    refresh();
    return created;
  };

  const deleteAnnotation = async (id) => {
    await apiDelete(`/api/annotations/${id}`);
    refresh();
  };

  const undo = async () => {
    const action = undoStack.current.pop();
    if (!action) return;
    await deleteAnnotation(action.id);
    redoStack.current.push(action);
    forceRender((n) => n + 1);
  };

  const redo = async () => {
    const action = redoStack.current.pop();
    if (!action) return;
    const created = await createAnnotation(action.data);
    action.id = created.id;
    undoStack.current.push(action);
    forceRender((n) => n + 1);
  };

  // Keyboard shortcuts.
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
      if (e.key.toLowerCase() === "e" && !e.metaKey && !e.ctrlKey) setTool("erase");
      if (e.key.toLowerCase() === "p" && !e.metaKey && !e.ctrlKey) setTool("pen");
      if (e.key.toLowerCase() === "h" && !e.metaKey && !e.ctrlKey) setTool("highlight");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  const onPointerDown = (e) => {
    const p = toNormalized(e);
    if (tool === "erase") {
      const hit = hitTestAnnotation(annotations, pageNum, p);
      if (hit) deleteAnnotation(hit.id);
      return;
    }
    setDrawing({ points: [p] });
  };

  const onPointerMove = (e) => {
    if (!drawing) return;
    const p = toNormalized(e);
    setDrawing((d) => ({ points: [...d.points, p] }));
  };

  const onPointerUp = async () => {
    if (drawing && drawing.points.length > 1) {
      await createAnnotation({
        page_number: pageNum,
        tool,
        color: tool === "highlight" ? HIGHLIGHT_COLOR : PEN_COLOR,
        stroke_width: tool === "highlight" ? 12 : 2,
        points: drawing.points.map((p) => [p.x, p.y]),
      });
    }
    setDrawing(null);
  };

  const pageAnnotations = annotations.filter((a) => a.page_number === pageNum && !a.deleted);
  const canUndo = undoStack.current.length > 0;
  const canRedo = redoStack.current.length > 0;

  if (file?.mime_type === "application/pdf" || file?.previewable) {
    return (
      <div className="document">
        <div className="doc-toolbar">
          <button className="wb-tool" onClick={() => navigate(-1)} title="Back">
            <ArrowLeft size={16} />
          </button>
          <span className="wb-sep" />
          <button
            className={`wb-tool ${tool === "pen" ? "wb-tool-active" : ""}`}
            onClick={() => setTool("pen")}
            title="Pen (P)"
          >
            <Pen size={16} />
          </button>
          <button
            className={`wb-tool ${tool === "highlight" ? "wb-tool-active" : ""}`}
            onClick={() => setTool("highlight")}
            title="Highlighter (H)"
          >
            <Highlighter size={16} />
          </button>
          <button
            className={`wb-tool ${tool === "erase" ? "wb-tool-active" : ""}`}
            onClick={() => setTool("erase")}
            title="Eraser (E)"
          >
            <Eraser size={16} />
          </button>

          <span className="wb-sep" />

          <button className="wb-tool" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
            <Undo2 size={16} />
          </button>
          <button className="wb-tool" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Y)">
            <Redo2 size={16} />
          </button>

          <span className="wb-sep" />

          <button className="wb-tool" onClick={() => setPageNum((p) => Math.max(1, p - 1))} disabled={pageNum <= 1}>
            <ChevronLeft size={16} />
          </button>
          <span className="doc-page-label">{pageNum} / {numPages || "…"}</span>
          <button className="wb-tool" onClick={() => setPageNum((p) => Math.min(numPages || p, p + 1))}>
            <ChevronRight size={16} />
          </button>
          <span className="wb-name">{file?.name}</span>
        </div>

        <div className="doc-canvas-wrap">
          {rendering && (
            <div className="doc-loading">
              <Spinner size={20} />
            </div>
          )}
          <div className="doc-stage">
            <canvas ref={canvasRef} className="doc-canvas" />
            <svg
              ref={overlayRef}
              className="doc-overlay"
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              style={{ cursor: tool === "erase" ? "crosshair" : "crosshair" }}
            >
              {pageAnnotations.map((a) => (
                <AnnotationView key={a.id} a={a} />
              ))}
              {drawing && (
                <path
                  d={drawing.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x * 100} ${p.y * 100}`).join(" ")}
                  stroke={tool === "highlight" ? HIGHLIGHT_COLOR : PEN_COLOR}
                  strokeWidth={tool === "highlight" ? 6 : 0.5}
                  fill="none"
                  strokeLinecap="round"
                  opacity={tool === "highlight" ? 0.35 : 1}
                />
              )}
            </svg>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page page-narrow">
      <h1 className="page-title">{file?.name}</h1>
      <p className="page-subtitle">This file type can only be downloaded.</p>
      <a className="btn btn-primary" href={`/api/vault/files/${fileId}/content`} style={{ marginTop: 16 }}>
        Download
      </a>
    </div>
  );
}

function hitTestAnnotation(annotations, pageNum, pt) {
  const threshold = 0.02; // 2% of the page
  let best = null;
  let bestDist = Infinity;
  for (const a of annotations) {
    if (a.page_number !== pageNum || a.deleted) continue;
    if (!a.points) continue;
    for (const p of a.points) {
      const d = Math.hypot(p[0] - pt.x, p[1] - pt.y);
      if (d < threshold && d < bestDist) {
        best = a;
        bestDist = d;
      }
    }
  }
  return best;
}

function AnnotationView({ a }) {
  if (a.tool === "text" || a.tool === "sticky") return null;
  const pts = (a.points || []).map((p) => ({ x: p[0] * 100, y: p[1] * 100 }));
  if (pts.length < 2) return null;
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  return (
    <path
      d={d}
      stroke={a.color || PEN_COLOR}
      strokeWidth={a.tool === "highlight" ? 6 : 0.5}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity={a.tool === "highlight" ? 0.35 : 1}
    />
  );
}
