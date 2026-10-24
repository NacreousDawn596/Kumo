import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { forceCenter, forceLink, forceManyBody, forceSimulation } from "d3-force";
import { select as d3select } from "d3-selection";
import { zoom as d3zoom } from "d3-zoom";
import { Network } from "lucide-react";
import { api } from "../api/client.js";
import { EmptyState } from "../components/ui.jsx";
import "../styles/pages.css";
import "./knowledge.css";

export default function KnowledgePage() {
  const navigate = useNavigate();
  const svgRef = useRef(null);

  const { data: graph } = useQuery({
    queryKey: ["graph"],
    queryFn: () => api("/api/knowledge/graph"),
  });

  useEffect(() => {
    if (!graph || graph.nodes.length === 0 || !svgRef.current) return;
    const svg = svgRef.current;
    const width = svg.clientWidth;
    const height = svg.clientHeight;

    const nodes = graph.nodes.map((n) => ({ ...n }));
    const links = graph.edges.map((e) => ({ ...e }));

    const simulation = forceSimulation(nodes)
      .force(
        "link",
        forceLink(links).id((d) => d.id).distance(90)
      )
      .force("charge", forceManyBody().strength(-220))
      .force("center", forceCenter(width / 2, height / 2));

    const g = d3select(svg);
    g.selectAll("*").remove();

    const link = g.append("g").selectAll("line").data(links).join("line").attr("class", "kg-link");
    const node = g
      .append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "kg-node")
      .style("cursor", "pointer")
      .on("click", (e, d) => navigate(`/pages/${d.id}`));

    node.append("circle").attr("r", 9);
    node
      .append("text")
      .attr("dy", 24)
      .attr("text-anchor", "middle")
      .text((d) => (d.label.length > 18 ? d.label.slice(0, 18) + "…" : d.label));

    const zoomBehavior = d3zoom().scaleExtent([0.2, 4]).on("zoom", (e) => g.attr("transform", e.transform));
    d3select(svg).call(zoomBehavior);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [graph, navigate]);

  const hasData = graph && graph.nodes.length > 0;

  return (
    <div className="knowledge-page">
      <div className="knowledge-head">
        <div>
          <h1 className="page-title">Knowledge graph</h1>
          <p className="page-subtitle">
            {hasData
              ? `${graph.nodes.length} notes, ${graph.edges.length} connections`
              : "Connect notes with links to grow your graph."}
          </p>
        </div>
      </div>

      {!hasData ? (
        <EmptyState
          icon={Network}
          title="Your graph is empty"
          description="Create notes and link them together to see relationships."
        />
      ) : (
        <svg ref={svgRef} className="kg-svg" />
      )}
    </div>
  );
}
