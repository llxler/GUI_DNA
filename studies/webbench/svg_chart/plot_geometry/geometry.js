() => {
  const roots = document.querySelectorAll('svg#lineAxes');
  if (roots.length !== 1) return {chartCount: roots.length};

  const svg = roots[0];
  const box = svg.viewBox.baseVal;
  const toLocal = el => svg.getScreenCTM().inverse().multiply(el.getScreenCTM());
  const coords = (point, matrix) => {
    const transformed = new DOMPoint(point.x, point.y).matrixTransform(matrix);
    return [transformed.x, transformed.y];
  };
  const visibleStroke = el => {
    if (!el.checkVisibility({opacityProperty: true, visibilityProperty: true})) return false;
    const style = getComputedStyle(el);
    return style.stroke !== 'none' && parseFloat(style.strokeOpacity) > 0 && parseFloat(style.strokeWidth) > 0;
  };
  const lines = Array.from(svg.querySelectorAll('.datasets polyline.dataset'), el =>
    ({visible: visibleStroke(el), points: Array.from(el.points, point => coords(point, toLocal(el)))}));
  const axis = direction => {
    const found = svg.querySelectorAll('.axes-' + direction + ' .axis-' + direction);
    if (found.length !== 1) return null;
    const el = found[0];
    if (!(el instanceof SVGGeometryElement) || !visibleStroke(el) || !el.getTotalLength()) return null;
    const matrix = toLocal(el);
    return [coords(el.getPointAtLength(0), matrix), coords(el.getPointAtLength(el.getTotalLength()), matrix)];
  };
  return {chartCount: 1, viewBox: [box.x, box.y, box.width, box.height], lines, xAxis: axis('x'), yAxis: axis('y')};
}
