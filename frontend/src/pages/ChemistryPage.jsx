import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Atom, RotateCcw } from "lucide-react";
import { apiPost } from "../api/client.js";
import { Button, Input } from "../components/ui.jsx";
import MoleculeViewer from "../components/MoleculeViewer.jsx";
import "../styles/pages.css";
import "./chemistry.css";

const EXAMPLES = [
  { label: "Ethanol", smiles: "CCO" },
  { label: "Benzene", smiles: "c1ccccc1" },
  { label: "Caffeine", smiles: "Cn1cnc2c1c(=O)n(C)c(=O)n2C" },
  { label: "Acetic acid", smiles: "CC(=O)O" },
  { label: "Glucose", smiles: "C(C1C(C(C(C(O1)O)O)O)O)O" },
  { label: "Ammonium", smiles: "[NH4+]" },
];

export default function ChemistryPage() {
  const [smiles, setSmiles] = useState("CCO");
  const [spin, setSpin] = useState(false);

  const analyze = useMutation({
    mutationFn: (s) => apiPost("/api/chemistry/molecule", { smiles: s }),
  });

  const data = analyze.data;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Chemistry</h1>
          <p className="page-subtitle">
            Enter a SMILES string to verify it and view its 3D structure.
          </p>
        </div>
      </div>

      <div className="chem-input-row">
        <Input
          placeholder="SMILES, e.g. CCO"
          value={smiles}
          onChange={(e) => setSmiles(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && analyze.mutate(smiles)}
        />
        <Button variant="primary" icon={Atom} loading={analyze.isPending} onClick={() => analyze.mutate(smiles)}>
          Build
        </Button>
      </div>

      <div className="chem-examples">
        {EXAMPLES.map((ex) => (
          <button key={ex.smiles} className="template-chip" onClick={() => { setSmiles(ex.smiles); analyze.mutate(ex.smiles); }}>
            {ex.label}
          </button>
        ))}
      </div>

      {analyze.error && <p className="auth-error">{(analyze.error.data?.detail) || "Failed to analyze."}</p>}
      {data && !data.valid && <p className="auth-error">{data.error}</p>}

      {data?.valid && (
        <div className="chem-layout">
          <div className="chem-viewer-col">
            <MoleculeViewer atoms={data.atoms} bonds={data.bonds} spin={spin} />
            <div className="chem-viewer-controls">
              <Button variant="secondary" icon={RotateCcw} onClick={() => setSpin((s) => !s)}>
                {spin ? "Stop spinning" : "Spin"}
              </Button>
              <span className="chem-hint">Drag to rotate · scroll to zoom</span>
            </div>
          </div>

          <div className="chem-info">
            <h2 className="section-title">Molecule</h2>
            <dl className="chem-props">
              <div><dt>Formula</dt><dd>{data.formula}</dd></div>
              <div><dt>Molecular weight</dt><dd>{data.molecular_weight} g/mol</dd></div>
              <div><dt>Heavy atoms</dt><dd>{data.num_atoms}</dd></div>
              <div><dt>Bonds</dt><dd>{data.num_bonds}</dd></div>
              <div><dt>Formal charge</dt><dd>{data.total_charge}</dd></div>
            </dl>

            <h2 className="section-title">Atoms</h2>
            <div className="chem-legend">
              {data.atoms.map((a, i) => (
                <span key={i} className="chem-legend-item">
                  <span className="chem-dot" style={{ background: a.color }} />
                  {a.symbol}{a.charge !== 0 ? `${a.charge > 0 ? "+" : ""}${a.charge}` : ""}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
