import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Highlighter, Pen } from "lucide-react";
import { api, apiGet, apiPost } from "../api/client.js";
import { Spinner } from "../components/ui.jsx";
import "./document.css";

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
  const queryClient = useQueryClient();
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const [pageNum, setPageNum] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [tool, setTool] = useState("pen");
  const [drawing, setDrawing] = useState(null);

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

  const onPointerDown = (e) => {
    const p = toNormalized(e);
    setDrawing({ points: [p] });
  };

  const onPointerMove = (e) => {
    if (!drawing) return;
    const p = toNormalized(e);
    setDrawing((d) => ({ points: [...d.points, p] }));
  };

  const onPointerUp = async () => {
    if (drawing && drawing.points.length > 1) {
      await apiPost(`/api/annotations/files/${fileId}`, {
        page_number: pageNum,
        tool,
        color: tool === "highlight" ? "#A66BFF" : "#A66BFF",
        stroke_width: tool === "highlight" ? 12 : 2,
        points: drawing.points.map((p) => [p.x, p.y]),
      });
      queryClient.invalidateQueries({ queryKey: ["annotations", fileId] });
    }
    setDrawing(null);
  };

  const pageAnnotations = annotations.filter((a) => a.page_number === pageNum);

  if (file?.mime_type === "application/pdf" || file?.previewable) {
    return (
      <div className="document">
        <div className="doc-toolbar">
          <button className={`wb-tool ${tool === "pen" ? "wb-tool-active" : ""}`} onClick={() => setTool("pen")}>
            <Pen size={16} />
          </button>
          <button className={`wb-tool ${tool === "highlight" ? "wb-tool-active" : ""}`} onClick={() => setTool("highlight")}>
            <Highlighter size={16} />
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
            >
              {pageAnnotations.map((a) => (
                <AnnotationView key={a.id} a={a} />
              ))}
              {drawing && (
                <path
                  d={drawing.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x * 100} ${p.y * 100}`).join(" ")}
                  stroke="#A66BFF"
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

function AnnotationView({ a }) {
  if (a.tool === "text" || a.tool === "sticky") {
    return null;
  }
  const pts = a.points.map((p) => ({ x: p[0] * 100, y: p[1] * 100 }));
  if (pts.length === 1) return null;
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  return (
    <path
      d={d}
      stroke={a.color || "#A66BFF"}
      strokeWidth={a.tool === "highlight" ? 6 : 0.5}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity={a.tool === "highlight" ? 0.35 : 1}
    />
  );
}
