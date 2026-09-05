"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";

interface TreeNode {
  name: string;
  children?: TreeNode[];
}

const nodeWidth = 200;
const nodeHeight = 50;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = "LR") => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === "LR";
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;

    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };

    return node;
  });

  return { nodes, edges };
};

function parseTreeToElements(root: TreeNode): { nodes: Node[], edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let idCounter = 1;

  function traverse(node: TreeNode, parentId: string | null = null) {
    const id = `node-${idCounter++}`;
    nodes.push({
      id,
      data: { label: node.name },
      position: { x: 0, y: 0 },
      type: "default",
      style: {
        background: "#171717",
        color: "#FFFFFF",
        border: "1px solid #2563EB",
        borderRadius: "8px",
        padding: "10px",
        fontSize: "14px",
        fontWeight: "bold",
        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      },
    });

    if (parentId) {
      edges.push({
        id: `e-${parentId}-${id}`,
        source: parentId,
        target: id,
        animated: true,
        style: { stroke: "#2563EB" },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#2563EB",
        },
      });
    }

    if (node.children && node.children.length > 0) {
      node.children.forEach((child) => traverse(child, id));
    }
  }

  traverse(root);
  return { nodes, edges };
}

interface MindMapViewerProps {
  data: TreeNode;
}

export default function MindMapViewer({ data }: MindMapViewerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (data) {
      const { nodes: initialNodes, edges: initialEdges } = parseTreeToElements(data);
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        initialNodes,
        initialEdges,
        "LR"
      );

      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
    }
  }, [data, setNodes, setEdges]);

  return (
    <div style={{ width: "100%", height: "100%" }} className="react-flow-dark">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        colorMode="dark"
        minZoom={0.2}
      >
        <Background color="#262626" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
