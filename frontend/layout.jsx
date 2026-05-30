/* global React */
// Aijolot Banner Agent — asymmetric banner-layout model + renderer.
// A layout is column-based: { cols: [ { rows, w }, ... ] }. Each column has its
// own number of rows (asymmetric) and a flex weight (relative width).

function layoutCells(layout) {
  const cols = (layout && layout.cols) || [{ rows: 1, w: 1 }];
  return cols.reduce((s, c) => s + c.rows, 0);
}

// Renders the layout, calling cell(index) for each cell in column-major order.
function BannerLayout({ layout, gap = 12, cell, minH }) {
  const cols = (layout && layout.cols) || [{ rows: 1, w: 1 }];
  let idx = -1;
  return (
    <div style={{ display: "flex", gap, width: "100%", height: "100%", alignItems: "stretch" }}>
      {cols.map((c, ci) => (
        <div key={ci} style={{ flex: c.w, display: "flex", flexDirection: "column", gap }}>
          {Array.from({ length: c.rows }).map((_, ri) => {
            idx += 1;
            const i = idx;
            return <div key={ri} style={{ flex: 1, minHeight: minH || 0, display: "flex" }}>{cell(i)}</div>;
          })}
        </div>
      ))}
    </div>
  );
}

// Small wireframe diagram of a layout (for the builder preview).
function LayoutDiagram({ layout, h = 70 }) {
  const cols = (layout && layout.cols) || [{ rows: 1, w: 1 }];
  const just = (a) => a === "left" ? "flex-start" : a === "right" ? "flex-end" : "center";
  return (
    <div style={{ display: "flex", gap: 4, height: h, width: "100%" }}>
      {cols.map((c, ci) => (
        <div key={ci} style={{ flex: c.w, display: "flex", flexDirection: "column", gap: 4 }}>
          {Array.from({ length: c.rows }).map((_, ri) => (
            <div key={ri} style={{ flex: 1, borderRadius: 4, background: "rgba(34,211,238,.1)", border: "1px solid rgba(34,211,238,.4)", display: "flex", alignItems: "center", justifyContent: just(c.align), padding: "0 6px" }}>
              <div style={{ height: 6, width: "52%", maxWidth: 64, borderRadius: 3, background: "rgba(34,211,238,.55)" }} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { layoutCells, BannerLayout, LayoutDiagram });
