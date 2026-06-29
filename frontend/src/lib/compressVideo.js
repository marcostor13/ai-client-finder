/**
 * In-browser video compression with ffmpeg.wasm.
 *
 * Re-encodes the selected file to an efficient H.264/AAC MP4 *before* upload, so
 * the upload is much smaller and faster with little to no visible quality loss.
 * Uses the single-thread core (no SharedArrayBuffer / COOP-COEP headers needed).
 */
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

const CORE_BASE = 'https://unpkg.com/@ffmpeg/core@0.12.10/dist/umd';

// Quality presets. `long` = cap for the longest side (0 = keep resolution).
const PRESETS = {
  high:     { long: 0,    crf: 23, label: 'Alta calidad (mantiene resolución)' },
  balanced: { long: 1920, crf: 26, label: 'Equilibrada (hasta 1080p)' },
  max:      { long: 1280, crf: 28, label: 'Máxima compresión (hasta 720p)' },
};

let _ffmpeg = null;
let _loadPromise = null;
let _progressCb = null;

export function compressionSupported() {
  return typeof WebAssembly === 'object';
}

async function getFFmpeg() {
  if (_ffmpeg) return _ffmpeg;
  if (!_loadPromise) {
    _loadPromise = (async () => {
      const ff = new FFmpeg();
      ff.on('progress', ({ progress }) => {
        if (_progressCb) _progressCb(Math.max(0, Math.min(1, progress || 0)));
      });
      await ff.load({
        coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, 'text/javascript'),
        wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, 'application/wasm'),
      });
      _ffmpeg = ff;
      return ff;
    })();
  }
  return _loadPromise;
}

/**
 * Compress `file`. Returns a new File (smaller MP4). Throws on failure so the
 * caller can fall back to uploading the original.
 *
 * @param {File} file
 * @param {{quality?: 'high'|'balanced'|'max', onProgress?: (p:number)=>void}} opts
 */
export async function compressVideo(file, { quality = 'balanced', onProgress } = {}) {
  const preset = PRESETS[quality] || PRESETS.balanced;
  const ff = await getFFmpeg();

  _progressCb = onProgress || null;
  const inName = 'input.bin';
  const outName = 'output.mp4';

  await ff.writeFile(inName, await fetchFile(file));

  const args = ['-i', inName];
  if (preset.long > 0) {
    args.push(
      '-vf',
      `scale='min(${preset.long},iw)':'min(${preset.long},ih)':` +
        `force_original_aspect_ratio=decrease:force_divisible_by=2`,
    );
  }
  args.push(
    '-c:v', 'libx264',
    '-crf', String(preset.crf),
    '-preset', 'veryfast',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-movflags', '+faststart',
    outName,
  );

  try {
    await ff.exec(args);
    const data = await ff.readFile(outName);
    const blob = new Blob([data.buffer], { type: 'video/mp4' });
    const base = (file.name || 'video').replace(/\.[^.]+$/, '');
    return new File([blob], `${base}-min.mp4`, { type: 'video/mp4' });
  } finally {
    _progressCb = null;
    try { await ff.deleteFile(inName); } catch {}
    try { await ff.deleteFile(outName); } catch {}
  }
}

export { PRESETS };
