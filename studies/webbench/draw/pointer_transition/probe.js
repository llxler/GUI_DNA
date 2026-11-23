// Observe one SVG line gesture in the root SVG's user coordinate system.
const svg = document.querySelector("svg.canvas");
const width = document.querySelector("input.line-width");
const tool = document.querySelector("label.line");
if (!svg || !width || !tool) return {status: "missing public SVG or controls"};
if (phase === "prepare") {
  width.value = "9";
  width.dispatchEvent(new Event("input", {bubbles: true}));
  width.dispatchEvent(new Event("change", {bubbles: true}));
  if (Number(width.value) !== 9) return {status: "width 9 unavailable"};
  tool.click();
  const matrix = svg.getScreenCTM();
  if (!matrix) return {status: "missing SVG coordinate system"};
  const a = new DOMPoint(80, 80).matrixTransform(matrix);
  const b = new DOMPoint(80 + distance, 80).matrixTransform(matrix);
  if (![a,b].every(p => svg.contains(document.elementFromPoint(p.x,p.y)))) {
    return {status: "unreachable gesture coordinates"};
  }
  window.__guiDnaExistingLines = new WeakSet(svg.querySelectorAll("line"));
  return {status: "ready", start: [a.x,a.y], end: [b.x,b.y]};
}
const fresh = Array.from(svg.querySelectorAll("line")).filter(line => {
  const style = getComputedStyle(line);
  return !window.__guiDnaExistingLines.has(line) && !line.closest("defs, pattern, marker, symbol")
         && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0
         && style.stroke !== "none" && Number(style.strokeOpacity) > 0;
});
if (fresh.length !== 1) return {status: "expected one new visible SVG line", count: fresh.length};
const line = fresh[0];
const toRoot = svg.getScreenCTM().inverse().multiply(line.getScreenCTM());
function point(x, y) {
  const p = new DOMPoint(line[x].baseVal.value, line[y].baseVal.value).matrixTransform(toRoot);
  return [p.x, p.y];
}
return {status: "line", start: point("x1","y1"), end: point("x2","y2"),
        width: getComputedStyle(line).strokeWidth};
