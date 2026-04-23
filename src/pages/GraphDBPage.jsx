// src/pages/GraphDBPage.jsx
import React, { useEffect, useState, useRef } from 'react';
import { api, Icons } from '../store';
import ForceGraph2D from 'react-force-graph-2d';

export default function GraphDBPage() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [stats, setStats] = useState({ total_nodes: 0, total_edges: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    api.getGraphData()
      .then(res => {
        setStats({ total_nodes: res.total_nodes, total_edges: res.total_edges });
        setGraphData({
          nodes: res.nodes,
          // Map backend links format to ForceGraph expected format
          links: res.links.map(link => ({
            source: link.source,
            target: link.target,
            name: link.relation
          }))
        });
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Update canvas dynamically when container size changes
  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.offsetWidth,
        height: 600 // Fixed height for visual consistency
      });
    }
    
    const handleResize = () => {
       if (containerRef.current) {
         setDimensions({ width: containerRef.current.offsetWidth, height: 600 });
       }
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [loading]);

  if (loading) return <div style={{ padding: '40px' }}>Loading Knowledge Graph...</div>;
  if (error) return <div style={{ padding: '40px', color: 'var(--error)' }}>Error loading graph: {error}</div>;

  return (
    <div className="page-container">
      <h2 style={{ fontSize: '1.5rem' }}>Knowledge Graph Visualization</h2>
      
      <div className="grid-2-col">
        <div className="dashboard-card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Total Graph Nodes</span>
          <span style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-primary)' }}>{stats.total_nodes}</span>
        </div>
        <div className="dashboard-card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Total Relationships (Edges)</span>
          <span style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-primary)' }}>{stats.total_edges}</span>
        </div>
      </div>

      <div 
        className="dashboard-card" 
        style={{ padding: 0, overflow: 'hidden', height: '600px', background: '#f8fafc', position: 'relative', border: '1px solid var(--border-medium)' }} 
        ref={containerRef}
      >
        {graphData.nodes.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Icons.Network />
            <h3 style={{ marginTop: '16px', color: 'var(--text-main)' }}>Graph is Empty</h3>
            <p style={{ marginTop: '8px' }}>Ensure "Graph RAG" is enabled in Settings and process some documents to see relationships here.</p>
          </div>
        ) : (
          <ForceGraph2D
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            nodeLabel="id"
            nodeAutoColorBy="id" // Automatically gives nodes a nice colorful distinct appearance
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkColor={() => '#94a3b8'} // Subtle line color
            
            // Custom Neo4j Style Node Rendering
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.id;
              const fontSize = 14 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              const textWidth = ctx.measureText(label).width;
              const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4); // padding

              ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'; // Node background
              ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = node.color || '#2563eb'; // Node text color
              ctx.fillText(label, node.x, node.y);

              node.__bckgDimensions = bckgDimensions; // Save for hover detection
            }}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              const bckgDimensions = node.__bckgDimensions;
              bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
            }}
            
            // Render Relationship names on edges
            linkCanvasObjectMode={() => 'after'}
            linkCanvasObject={(link, ctx, globalScale) => {
              const start = link.source;
              const end = link.target;
              
              if (typeof start !== 'object' || typeof end !== 'object') return;
              
              const textPos = Object.assign(...['x', 'y'].map(c => ({
                [c]: start[c] + (end[c] - start[c]) / 2 // Find middle of the line
              })));
              
              const relLink = { x: end.x - start.x, y: end.y - start.y };
              let textAngle = Math.atan2(relLink.y, relLink.x);
              
              // Maintain label upright positioning
              if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
              if (textAngle < -Math.PI / 2) textAngle = -(Math.PI + textAngle);
              
              const fontSize = 10 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              
              ctx.save();
              ctx.translate(textPos.x, textPos.y);
              ctx.rotate(textAngle);
              
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#64748b'; // Text color for edge labels
              
              // Add a tiny white background to the text for readability over lines
              ctx.fillText(link.name, 0, -2);
              ctx.restore();
            }}
          />
        )}
      </div>
    </div>
  );
}