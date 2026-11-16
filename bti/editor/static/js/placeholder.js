// Placeholder frame generator (mock mode): draws a synthetic "painting" through the camera mapping,
// so the draggable handles line up with what is drawn. Also used as the source view fallback.
import { makeMapping, fitCamera, cameraAt, shotIndexAt } from './logic.js';

const HUES = { A: 28, B: 212, C: 140 };
const hue = (key) => HUES[key] ?? ((key.charCodeAt(0) * 47) % 360);

export function paintAsset(ctx, key, asset, cam, canvas, W, H) {
  const m = makeMapping(cam, canvas, { W, H });
  const [x0, y0] = m.toScreen(0, 0), [x1, y1] = m.toScreen(asset.width, asset.height);
  const g = ctx.createLinearGradient(x0, y0, x1, y1);
  const h = hue(key);
  g.addColorStop(0, `hsl(${h} 45% 24%)`); g.addColorStop(0.5, `hsl(${h + 20} 40% 36%)`); g.addColorStop(1, `hsl(${h - 20} 50% 18%)`);
  ctx.fillStyle = g; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  ctx.save(); ctx.beginPath(); ctx.rect(x0, y0, x1 - x0, y1 - y0); ctx.clip();
  const step = 500 * Math.max(1, Math.ceil(90 / (500 * m.k)));
  ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.font = `${Math.max(9, 11)}px sans-serif`;
  for (let x = 0; x <= asset.width; x += step) { const [sx] = m.toScreen(x, 0); ctx.beginPath(); ctx.moveTo(sx, y0); ctx.lineTo(sx, y1); ctx.stroke(); }
  for (let y = 0; y <= asset.height; y += step) { const [, sy] = m.toScreen(0, y); ctx.beginPath(); ctx.moveTo(x0, sy); ctx.lineTo(x1, sy); ctx.stroke(); }
  for (let x = 0; x <= asset.width; x += step) for (let y = 0; y <= asset.height; y += step) {
    const [sx, sy] = m.toScreen(x, y);
    if (sx > -40 && sx < W && sy > -10 && sy < H + 10 && m.k > 0.05) ctx.fillText(`${x},${y}`, sx + 3, sy + 12);
  }
  // fake figures so the picture is not blank
  ctx.fillStyle = `hsla(${h + 160} 30% 60% / 0.35)`;
  const fig = (cx, cy, rx, ry) => { const [sx, sy] = m.toScreen(cx, cy); ctx.beginPath(); ctx.ellipse(sx, sy, rx * m.k, ry * m.k, 0, 0, 7); ctx.fill(); };
  fig(asset.width * 0.35, asset.height * 0.55, asset.width * 0.1, asset.height * 0.3);
  fig(asset.width * 0.65, asset.height * 0.55, asset.width * 0.09, asset.height * 0.28);
  fig(asset.width * 0.5, asset.height * 0.3, asset.width * 0.1, asset.width * 0.1);
  for (const r of Object.values(asset.regions || {})) {
    const [sx, sy] = m.toScreen(r.x, r.y);
    ctx.strokeStyle = 'rgba(255,214,102,.7)'; ctx.setLineDash([6, 4]); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.ellipse(sx, sy, r.rx * m.k, r.ry * m.k, 0, 0, 7); ctx.stroke(); ctx.setLineDash([]);
  }
  ctx.restore();
  ctx.fillStyle = '#fff'; ctx.font = 'bold 13px sans-serif';
  ctx.fillText(`${asset.title || key} (${asset.width}x${asset.height})`, Math.max(8, x0 + 8), Math.max(18, y0 + 18));
  return m;
}

/** Render a mock engine frame for a resolved storyboard at time t. Returns a canvas. */
export function renderMockFrame(sb, t, width) {
  const W = width, H = Math.round((width * 9) / 16);
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  const canvas = sb.canvas || { w: 1920, h: 1080 };
  const shot = sb.shots[shotIndexAt(sb.shots, t)];
  ctx.fillStyle = '#050505'; ctx.fillRect(0, 0, W, H);
  const slotAssets = Object.entries(shot.slots || {}).map(([n, v]) => [n, v?.asset]).filter(([, a]) => a && sb.assets[a]);
  const camKeys = shot.params?.camera;
  if (camKeys?.length && slotAssets.length) {
    const cam = cameraAt(camKeys, t);
    const [, key] = slotAssets[0];
    paintAsset(ctx, key, sb.assets[key], cam, canvas, W, H);
  } else if (slotAssets.length) {
    const n = slotAssets.length, pw = W / n;
    slotAssets.forEach(([, key], i) => {
      ctx.save(); ctx.beginPath(); ctx.rect(i * pw + 4, 0, pw - 8, H); ctx.clip();
      ctx.translate(i * pw, 0);
      paintAsset(ctx, key, sb.assets[key], fitCamera(sb.assets[key], { w: canvas.w / n, h: canvas.h }), { w: canvas.w / n, h: canvas.h }, pw, H);
      ctx.restore();
    });
  } else {
    ctx.fillStyle = '#111'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#e8e8e8'; ctx.font = `bold ${H / 10}px serif`; ctx.textAlign = 'center';
    ctx.fillText(shot.params?.title || shot.technique, W / 2, H / 2); ctx.textAlign = 'left';
  }
  // overlays active now
  for (const o of shot.overlays || []) {
    if (t < o._t0 || t > o._t1) continue;
    ctx.fillStyle = 'rgba(79,156,255,.85)'; ctx.font = `${Math.round(H / 24)}px sans-serif`;
    ctx.fillText(`${o.technique}${o.params?.text ? ': ' + o.params.text : ''}`, 14, H - 16 - 22 * (shot.overlays.indexOf(o)));
  }
  ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(0, 0, W, 22);
  ctx.fillStyle = '#9fd0ff'; ctx.font = '12px monospace';
  ctx.fillText(`MOCK  ${shot.id}  ${shot.technique}  t=${t.toFixed(2)}s`, 8, 15);
  return c;
}

export function thumbDataUrl(sb, shot) {
  const mid = (shot._t0 + shot._t1) / 2;
  return renderMockFrame(sb, mid, 160).toDataURL('image/jpeg', 0.7);
}

export function assetThumb(key, asset) {
  const c = document.createElement('canvas'); c.width = 160; c.height = 120;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 160, 120);
  const cam = fitCamera(asset, { w: 160, h: 120 });
  paintAsset(ctx, key, { ...asset, regions: {} }, cam, { w: 160, h: 120 }, 160, 120);
  return c.toDataURL('image/jpeg', 0.7);
}
