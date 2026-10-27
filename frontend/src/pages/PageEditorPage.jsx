import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Code,
  Heading,
  Link2,
  List,
  ListChecks,
  ListOrdered,
  Minus,
  Quote,
  Sigma,
  Text,
  Undo2,
} from "lucide-react";
import { api, apiPatch } from "../api/client.js";
import { EmptyState, IconButton, Menu } from "../components/ui.jsx";
import Markdown from "../components/Markdown.jsx";
import "../styles/pages.css";
import "./editor.css";

const BLOCK_TYPES = [
  { id: "paragraph", label: "Text", icon: Text },
  { id: "heading", label: "Heading", icon: Heading },
  { id: "bullet", label: "Bulleted list", icon: List },
  { id: "numbered", label: "Numbered list", icon: ListOrdered },
  { id: "todo", label: "Checklist", icon: ListChecks },
  { id: "quote", label: "Quote", icon: Quote },
  { id: "code", label: "Code", icon: Code },
  { id: "divider", label: "Divider", icon: Minus },
  { id: "math", label: "Equation", icon: Sigma },
];

function debounce(fn, ms) {
  let t;
  const debounced = (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
  debounced.cancel = () => clearTimeout(t);
  debounced.flush = (...args) => {
    clearTimeout(t);
    fn(...args);
  };
  return debounced;
}

export default function PageEditorPage() {
  const { pageId } = useParams();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [blocks, setBlocks] = useState([]);
  const initializedFor = useRef(null);

  const { data: page, isLoading } = useQuery({
    queryKey: ["page", pageId],
    queryFn: () => api(`/api/pages/${pageId}`),
  });

  useEffect(() => {
    if (page && initializedFor.current !== pageId) {
      setTitle(page.title);
      setBlocks(
        page.blocks.map((b) => ({
          id: b.id,
          block_type: b.block_type,
          content: b.content || "",
          properties: b.properties,
        }))
      );
      initializedFor.current = pageId;
    }
  }, [page, pageId]);

  const { data: backlinks = [] } = useQuery({
    queryKey: ["backlinks", pageId],
    queryFn: () => api(`/api/pages/${pageId}/backlinks`),
  });

  const saveTitle = useMutation({
    mutationFn: (t) => apiPatch(`/api/pages/${pageId}`, { title: t }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pages"] }),
  });

  const saveBlocks = useMutation({
    mutationFn: ({ bs }) => api(`/api/pages/${pageId}/blocks`, { method: "PUT", body: bs }),
  });

  const blocksRef = useRef([]);
  const dirtyRef = useRef(false);

  useEffect(() => {
    blocksRef.current = blocks;
  }, [blocks]);

  const doSave = () => {
    if (!dirtyRef.current) return;
    dirtyRef.current = false;
    saveBlocks.mutate({
      bs: blocksRef.current.map(({ id, block_type, content }) => ({ id, block_type, content })),
    });
  };

  const debouncedSaveTitle = useRef(debounce((t) => saveTitle.mutate(t), 500)).current;
  const debouncedSaveBlocks = useRef(debounce(doSave, 600)).current;

  const persist = (next) => {
    setBlocks(next);
    dirtyRef.current = true;
    debouncedSaveBlocks();
  };

  // Flush any pending block save when the user navigates away, blurs, or unmounts.
  const flushRef = useRef(null);
  useEffect(() => {
    flushRef.current = () => {
      debouncedSaveBlocks.cancel();
      doSave();
    };
  });

  useEffect(() => {
    const flush = () => flushRef.current?.();
    window.addEventListener("beforeunload", flush);
    return () => {
      window.removeEventListener("beforeunload", flush);
      flushRef.current?.();
    };
  }, []);

  const updateBlock = (id, patch) => {
    persist(blocks.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  };

  const insertBlock = (index, type = "paragraph") => {
    const newBlock = { id: null, block_type: type, content: "" };
    const next = [...blocks];
    next.splice(index, 0, newBlock);
    persist(next);
    return index;
  };

  const removeBlock = (id) => {
    if (blocks.length <= 1) return;
    persist(blocks.filter((b) => b.id !== id));
  };

  const changeType = (id, type) => updateBlock(id, { block_type: type });

  if (isLoading) return <div className="page page-narrow" />;

  return (
    <div className="page editor-page" onBlur={() => flushRef.current?.()}>
      <div className="editor-toolbar">
        <Link to="/notes" className="btn btn-ghost btn-sm">
          <Undo2 size={14} /> Notes
        </Link>
      </div>

      <div className="editor">
        <input
          className="editor-title"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            debouncedSaveTitle(e.target.value);
          }}
          placeholder="Untitled"
        />

        {blocks.map((block, i) => (
          <Block
            key={block.id || `new-${i}`}
            block={block}
            autoFocus={block.id === null}
            onChange={(patch) => updateBlock(block.id, patch)}
            onChangeType={(type) => changeType(block.id, type)}
            onEnter={() => {
              insertBlock(i + 1);
              setTimeout(() => {
                const inputs = document.querySelectorAll("[data-block-input]");
                inputs[i + 1]?.focus();
              }, 0);
            }}
            onBackspace={() => removeBlock(block.id)}
            onDelete={() => removeBlock(block.id)}
          />
        ))}
      </div>

      {backlinks.length > 0 && (
        <div className="backlinks">
          <h3 className="backlinks-title">Backlinks</h3>
          {backlinks.map((b) => (
            <Link key={b.source_id} to={`/pages/${b.source_id}`} className="backlink-item">
              <Link2 size={14} />
              <span>{b.source_title}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Block({ block, autoFocus, onChange, onChangeType, onEnter, onBackspace, onDelete }) {
  const ref = useRef(null);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  if (block.block_type === "divider") {
    return (
      <div className="block block-divider">
        <hr />
        <BlockMenu onChangeType={onChangeType} onDelete={onDelete} />
      </div>
    );
  }

  if (block.block_type === "code") {
    return (
      <div className="block block-code">
        <textarea
          ref={ref}
          data-block-input
          className="code-input"
          value={block.content}
          onChange={(e) => onChange({ content: e.target.value })}
          placeholder="// code"
          rows={Math.max(2, block.content.split("\n").length)}
        />
        <BlockMenu onChangeType={onChangeType} onDelete={onDelete} />
      </div>
    );
  }

  if (block.block_type === "math") {
    return (
      <div className="block block-math">
        <textarea
          ref={ref}
          data-block-input
          className="math-input"
          value={block.content}
          onChange={(e) => onChange({ content: e.target.value })}
          placeholder="e^{i\pi} + 1 = 0"
          rows={1}
        />
        {block.content && <Markdown>{`$$\n${block.content}\n$$`}</Markdown>}
        <BlockMenu onChangeType={onChangeType} onDelete={onDelete} />
      </div>
    );
  }

  const prefix =
    block.block_type === "todo" ? (
      <input
        type="checkbox"
        className="todo-check"
        checked={!!block.properties?.checked}
        onChange={(e) => onChange({ properties: { checked: e.target.checked } })}
      />
    ) : block.block_type === "bullet" ? (
      <span className="bullet-dot" />
    ) : null;

  const textareaClass =
    block.block_type === "heading" ? "block-input heading-input" : "block-input";

  return (
    <div className="block">
      {prefix}
      <textarea
        ref={ref}
        data-block-input
        className={textareaClass}
        value={block.content}
        onChange={(e) => onChange({ content: e.target.value })}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onEnter();
          }
          if (e.key === "Backspace" && !block.content) {
            e.preventDefault();
            onBackspace();
          }
        }}
        placeholder={block.block_type === "heading" ? "Heading" : "Write something…"}
        rows={1}
      />
      <BlockMenu onChangeType={onChangeType} onDelete={onDelete} />
    </div>
  );
}

function BlockMenu({ onChangeType, onDelete }) {
  return (
    <div className="block-menu">
      <Menu
        trigger={<IconButton icon={Text} label="Block type" size="sm" />}
        items={[
          ...BLOCK_TYPES.map((t) => ({
            label: t.label,
            icon: t.icon,
            onClick: () => onChangeType(t.id),
          })),
          { divider: true },
          { label: "Delete block", danger: true, onClick: onDelete },
        ]}
      />
    </div>
  );
}
