"use client";

import { useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { Dossier } from "@/src/lib/types";

interface NetworkGraphProps {
  dossier: Dossier;
  className?: string;
}

interface GraphNode {
  id: string;
  name: string;
  type: "person" | "handle" | "company" | "coworker" | "email";
  confidence?: number;
  platform?: string;
}

interface GraphLink {
  source: string;
  target: string;
  label?: string;
}

export function NetworkGraph({ dossier, className }: NetworkGraphProps) {
  const graphRef = useRef<any>();

  // Transform dossier data into graph format
  const graphData = {
    nodes: [] as GraphNode[],
    links: [] as GraphLink[],
  };

  // Central node: The person
  const personId = "person";
  graphData.nodes.push({
    id: personId,
    name: dossier.metadata.identifierSummary || "Subject",
    type: "person",
  });

  // Add handle nodes
  dossier.handles.forEach((handle) => {
    const nodeId = `handle-${handle.platform}-${handle.username}`;
    graphData.nodes.push({
      id: nodeId,
      name: handle.username,
      type: "handle",
      confidence: handle.confidence,
      platform: handle.platform,
    });
    graphData.links.push({
      source: personId,
      target: nodeId,
      label: handle.platform,
    });
  });

  // Add company nodes from jobs
  const companies = new Set<string>();
  dossier.jobs.forEach((job) => {
    if (!companies.has(job.company)) {
      companies.add(job.company);
      const nodeId = `company-${job.company}`;
      graphData.nodes.push({
        id: nodeId,
        name: job.company,
        type: "company",
      });
      graphData.links.push({
        source: personId,
        target: nodeId,
        label: job.title,
      });
    }
  });

  // Add coworker nodes (limited to first 10)
  dossier.coworkers.slice(0, 10).forEach((coworker) => {
    const nodeId = `coworker-${coworker}`;
    graphData.nodes.push({
      id: nodeId,
      name: coworker,
      type: "coworker",
    });
    graphData.links.push({
      source: personId,
      target: nodeId,
      label: "coworker",
    });
  });

  // Add email domain nodes
  const emailDomains = new Set<string>();
  [...dossier.emails, ...dossier.verifiedEmails.map((e) => e.value)].forEach((email) => {
    const domain = email.split("@")[1];
    if (domain && !emailDomains.has(domain)) {
      emailDomains.add(domain);
      const nodeId = `email-${domain}`;
      graphData.nodes.push({
        id: nodeId,
        name: domain,
        type: "email",
      });
      graphData.links.push({
        source: personId,
        target: nodeId,
        label: "email",
      });
    }
  });

  // Node colors by type
  const getNodeColor = (node: GraphNode) => {
    switch (node.type) {
      case "person":
        return "#3b82f6"; // blue-500
      case "handle":
        return "#10b981"; // green-500
      case "company":
        return "#f59e0b"; // amber-500
      case "coworker":
        return "#8b5cf6"; // violet-500
      case "email":
        return "#ec4899"; // pink-500
      default:
        return "#6b7280"; // gray-500
    }
  };

  // Node size based on confidence
  const getNodeSize = (node: GraphNode) => {
    if (node.type === "person") return 8;
    if (node.confidence) return 3 + node.confidence * 5;
    return 4;
  };

  useEffect(() => {
    if (graphRef.current) {
      // Zoom to fit all nodes
      graphRef.current.zoomToFit(400, 50);
    }
  }, []);

  return (
    <div className={className} style={{ height: "600px", width: "100%" }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeLabel={(node: any) =>
          `${node.name}${node.confidence ? ` (${Math.round(node.confidence * 100)}%)` : ""}`
        }
        nodeColor={(node: any) => getNodeColor(node)}
        nodeVal={(node: any) => getNodeSize(node)}
        linkLabel="label"
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={2}
        linkColor={() => "rgba(0,0,0,0.2)"}
        backgroundColor="transparent"
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />
    </div>
  );
}
