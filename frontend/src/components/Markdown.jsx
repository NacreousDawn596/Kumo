import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

// KaTeX emits MathML (<math>, <mrow>, …) plus visual <span>s with class/style
// attributes. The default sanitize schema strips all of these, which silently
// breaks LaTeX. Extend it to allow KaTeX's output.
const KATEX_TAGS = [
  "math", "semantics", "annotation", "mrow", "mi", "mo", "mn", "ms", "mtext",
  "mspace", "msup", "msub", "msubsup", "mfrac", "munder", "mover", "munderover",
  "mstyle", "merror", "mpadded", "mphantom", "msqrt", "mroot", "menclose",
  "mfenced", "mtable", "mtr", "mtd",
];

const katexSchema = {
  ...defaultSchema,
  tagNames: [...defaultSchema.tagNames, ...KATEX_TAGS],
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes.span || []), "className", "style"],
    div: [...(defaultSchema.attributes.div || []), "className", "style"],
    math: ["xmlns", "display", "overflow", "className", "style"],
    annotation: ["encoding"],
  },
};

export default function Markdown({ children }) {
  const content = useMemo(() => children ?? "", [children]);
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, [rehypeSanitize, katexSchema]]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
