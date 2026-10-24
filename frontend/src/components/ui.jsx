import { forwardRef, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import "./ui.css";

export function Spinner({ size = 16 }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden />;
}

export function Button({
  children,
  variant = "secondary",
  size = "md",
  icon: Icon,
  loading,
  disabled,
  className = "",
  ...rest
}) {
  const cls = `btn btn-${variant} btn-${size} ${className}`;
  return (
    <button className={cls} disabled={disabled || loading} {...rest}>
      {loading ? (
        <Spinner size={15} />
      ) : (
        Icon && <Icon size={15} strokeWidth={2} aria-hidden />
      )}
      {children}
    </button>
  );
}

export function IconButton({ icon: Icon, label, size = "md", className = "", ...rest }) {
  return (
    <button className={`icon-btn icon-btn-${size} ${className}`} aria-label={label} title={label} {...rest}>
      <Icon size={size === "sm" ? 15 : 17} strokeWidth={2} aria-hidden />
    </button>
  );
}

export const Input = forwardRef(function Input({ className = "", invalid, ...rest }, ref) {
  return <input ref={ref} className={`input ${invalid ? "input-invalid" : ""} ${className}`} {...rest} />;
});

export const Textarea = forwardRef(function Textarea({ className = "", ...rest }, ref) {
  return <textarea ref={ref} className={`input textarea ${className}`} {...rest} />;
});

export function Select({ className = "", children, ...rest }) {
  return (
    <select className={`input select ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Avatar({ name, size = 28, src }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.42 }}>
      {src ? <img src={src} alt="" loading="lazy" /> : initial}
    </span>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="empty-state">
      {Icon && (
        <span className="empty-state-icon">
          <Icon size={22} strokeWidth={1.6} />
        </span>
      )}
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-desc">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}

export function Dialog({ open, onClose, title, children, footer, width = 420 }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="dialog-overlay" onMouseDown={onClose}>
      <div
        className="dialog"
        style={{ maxWidth: width }}
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="dialog-header">
          <h2 className="dialog-title">{title}</h2>
          <IconButton icon={X} label="Close" size="sm" onClick={onClose} />
        </div>
        <div className="dialog-body">{children}</div>
        {footer && <div className="dialog-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}

export function Menu({ trigger, items, align = "left" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="menu-root" ref={ref}>
      <span onClick={() => setOpen((o) => !o)}>{trigger}</span>
      {open && (
        <div className={`menu ${align === "right" ? "menu-right" : ""}`} role="menu">
          {items.map((item, i) =>
            item.divider ? (
              <div key={i} className="menu-divider" />
            ) : (
              <button
                key={i}
                className={`menu-item ${item.danger ? "menu-item-danger" : ""}`}
                onClick={() => {
                  setOpen(false);
                  item.onClick?.();
                }}
              >
                {item.icon && <item.icon size={15} strokeWidth={2} />}
                {item.label}
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}
