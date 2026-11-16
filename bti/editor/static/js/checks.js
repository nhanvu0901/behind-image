// Client-side checks the server does not make (advisory, level "warn"). They are merged into the issue list the server returns.
import { paramSpace, splitSpace, resolvePoint, outsideImage } from './coords.js';

const imageOf = (draft, slots) => {
  for (const v of Object.values(slots || {})) { const a = v?.asset && draft.assets[v.asset]; if (a && a.width && a.height && (a.kind || 'image') === 'image') return a; }
  return null;
};

/** Points of source-pixel parameters that lie outside their picture (U2-005). */
export function outsideIssues(draft, techOf) {
  const out = [];
  draft.shots.forEach((s, si) => {
    const base = `shots[${si}]`;
    const items = [{ it: s, path: base }, ...(s.overlays || []).map((o, oi) => ({ it: o, path: `${base}.overlays[${oi}]` }))];
    for (const { it, path } of items) {
      const tech = techOf(it.technique);
      if (!tech) continue;
      const hasSlot = (n) => !!(it.slots?.[n]?.asset || s.slots?.[n]?.asset);
      for (const def of tech.params) {
        if (def.type !== 'point' && def.type !== 'points') continue;
        const v = it.params?.[def.name];
        if (v === null || v === undefined) continue;
        const { space, slot } = splitSpace(paramSpace(tech.id, def, { params: it.params || {}, hasSlot }));
        if (space !== 'source') continue;
        const asset = slot ? draft.assets[it.slots?.[slot]?.asset || s.slots?.[slot]?.asset] : (imageOf(draft, it.slots && it !== s ? { ...s.slots, ...it.slots } : s.slots));
        if (!asset?.width) continue;
        const pts = def.type === 'points' ? (Array.isArray(v) ? v : []) : [v];
        pts.forEach((pv, i) => {
          const p = resolvePoint(pv, asset.regions);
          if (p && outsideImage(p, asset)) out.push({ level: 'warn', code: 'outside_image', path: `${path}.params.${def.name}`,
            message: `${def.name}${def.type === 'points' ? ` #${i + 1}` : ''}: điểm (${Math.round(p[0])}, ${Math.round(p[1])}) nằm ngoài ảnh ${asset.width} x ${asset.height} px` });
        });
      }
    }
  });
  return out;
}
