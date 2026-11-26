async () => {
  const {LineChart} = await import('/common/LineChart.js');
  const {BarChart} = await import('/common/BarChart.js');
  const results = {};
  const fixtures = [
    {labels:['Fir','Elm','Oak'], values:[[2,9,5],[7,4,3]]},
    {labels:['Red','Ochre','Blue','Green'], values:[[8,2,7,4],[1,9,3,6]]},
  ];
  for (const [group, fixture] of fixtures.entries()) {
    for (const [kind, Renderer] of [['line',LineChart], ['bar',BarChart]]) {
      for (const enabled of [false,true]) {
        const id = 'probe-' + group + '-' + kind + '-' + Number(enabled);
        const data = {labels:fixture.labels, datasets:fixture.values.map((data, i) => ({label:'series-' + i, data}))};
        const options = {axes:enabled,grids:enabled,legends:enabled,pointStyle:enabled?'circle':undefined,dataLabels:enabled};
        const r = {};
        try {
          const chart = new Renderer({id,type:kind,data,options});
          const svg = chart.svg;
          document.body.append(svg);
          chart.draw();
          const q = selector => Array.from(svg.querySelectorAll(selector));
          const box = svg.viewBox.baseVal;
          r.frame = svg.id===id && svg.classList.contains('chart') && svg.classList.contains(kind) &&
                    box.x===0 && box.y===0 && box.width===100 && box.height===70;
          const axes = q('.axes-x .axis-x, .axes-y .axis-y');
          r.axes = enabled ? axes.length>=2 : !q('.axes').length;
          r.grids = enabled ? q('.grids .grid').length>=fixture.labels.length : !q('.grids').length;
          r.legends = enabled ? data.datasets.every(s=>q('.legends text').some(x=>x.textContent.trim()===s.label)) : !q('.legends').length;
          r.labels = enabled ? fixture.labels.every(l=>q('.axes-x text').some(x=>x.textContent.trim()===l)) : !q('.axes-x text').length;
          if (kind==='line') {
            const series=q('.datasets polyline.dataset');
            const lines=series.map(s=>Array.from(s.points));
            r.series=lines.length===2 && lines.every(a=>a.length===fixture.labels.length && a.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
            const minima=Math.min(...fixture.values.flat()), maxima=Math.max(...fixture.values.flat());
            r.scale=r.series && lines.every((line,i)=>line.every((pt,j)=> {
              const last=line.length-1;
              if (j && pt.x<=line[j-1].x) return false;
              const first=lines.flatMap((ln,k)=>ln.filter((_,h)=>fixture.values[k][h]===minima))[0];
              const top=lines.flatMap((ln,k)=>ln.filter((_,h)=>fixture.values[k][h]===maxima))[0];
              const phase=(fixture.values[i][j]-minima)/(maxima-minima);
              return first.y-top.y>10 && Math.abs(pt.y-(first.y+phase*(top.y-first.y)))<0.6 && line[last].x-line[0].x>40;
            }));
            r.points=enabled ? q('.points circle').length===fixture.labels.length*2 : !q('.points circle').length;
            r.values=enabled ? q('.dataLabels text').length===fixture.labels.length*2 : !q('.dataLabels text').length;
          } else {
            const bars=q('.datasets rect');
            r.bars=bars.length===fixture.labels.length*2 && bars.every(b=>b.width.baseVal.value>0 && b.height.baseVal.value>=0);
          }
          svg.remove();
        } catch (error) {r.error=String(error).slice(0,180);}
        results[id]=r;
      }
    }
  }
  return results;
}
