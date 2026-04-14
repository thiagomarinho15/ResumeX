const MAX_BYTES = 24 * 1024 * 1024; // 24 MB per Groq API limit
const API_URL = '/transcrever';

// ─── DOM refs ────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const dropZone     = $('dropZone');
const fileInput    = $('fileInput');
const fileInfo     = $('fileInfo');
const fileName     = $('fileName');
const fileSize     = $('fileSize');
const removeBtn    = $('removeBtn');
const transcribeBtn = $('transcribeBtn');
const progressWrap = $('progressWrap');
const progressLabel = $('progressLabel');
const progressPct  = $('progressPct');
const progressFill = $('progressFill');
const logLine      = $('logLine');
const resultWrap   = $('resultWrap');
const resultBox    = $('resultBox');
const wordCount    = $('wordCount');
const copyBtn      = $('copyBtn');
const errorBox     = $('errorBox');

// ─── State ───────────────────────────────────────────────────────────────────

let selectedFile = null;

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt = (bytes) =>
  bytes < 1_048_576
    ? (bytes / 1_024).toFixed(1) + ' KB'
    : (bytes / 1_048_576).toFixed(1) + ' MB';

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.add('visible');
}

function hideError() {
  errorBox.classList.remove('visible');
}

function setProgress(pct, label, log) {
  progressFill.style.width = pct + '%';
  progressLabel.textContent = label;
  progressPct.textContent = pct ? pct + '%' : '';
  if (log !== undefined) logLine.textContent = log;
}

function setFile(file) {
  if (!file) return;
  hideError();
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = fmt(file.size);
  fileInfo.classList.add('visible');
  transcribeBtn.disabled = false;
  resultWrap.classList.remove('visible');
}

// ─── Audio processing ────────────────────────────────────────────────────────

/**
 * Encodes a Float32Array of PCM samples as a 16-bit mono WAV Blob.
 * Each chunk gets its own complete WAV header so the Groq API can parse it.
 */
function encodeWAV(samples, sr) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);

  const ws = (offset, str) => {
    for (let i = 0; i < str.length; i++) v.setUint8(offset + i, str.charCodeAt(i));
  };

  ws(0, 'RIFF');  v.setUint32(4, 36 + samples.length * 2, true);
  ws(8, 'WAVE');  ws(12, 'fmt ');
  v.setUint32(16, 16, true);   // PCM chunk size
  v.setUint16(20, 1, true);    // PCM format
  v.setUint16(22, 1, true);    // mono
  v.setUint32(24, sr, true);   // sample rate
  v.setUint32(28, sr * 2, true); // byte rate
  v.setUint16(32, 2, true);    // block align
  v.setUint16(34, 16, true);   // bits per sample
  ws(36, 'data'); v.setUint32(40, samples.length * 2, true);

  for (let i = 0, offset = 44; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  return new Blob([buf], { type: 'audio/wav' });
}

/**
 * Decodes the video/audio file and resamples to mono 16 kHz.
 * Returns the rendered AudioBuffer (raw PCM samples).
 */
async function extractAudio(file) {
  setProgress(5, 'Lendo vídeo…', 'Carregando na memória');
  const arrayBuffer = await file.arrayBuffer();

  setProgress(15, 'Decodificando áudio…', 'Extraindo faixa de áudio');
  const ctx = new AudioContext({ sampleRate: 16_000 });
  let decoded;
  try {
    decoded = await ctx.decodeAudioData(arrayBuffer);
  } finally {
    ctx.close();
  }

  setProgress(30, 'Renderizando mono 16 kHz…', `Duração: ${decoded.duration.toFixed(0)}s`);
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16_000), 16_000);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();

  setProgress(50, 'Áudio extraído!', `Duração: ${rendered.duration.toFixed(0)}s`);
  return rendered;
}

// ─── Transcription ───────────────────────────────────────────────────────────

async function transcribeChunk(wavBlob, index, total) {
  const form = new FormData();
  form.append('file', wavBlob, `part_${index}.wav`);
  form.append('model', 'whisper-large-v3');
  form.append('language', 'pt');
  form.append('response_format', 'text');

  const response = await fetch(API_URL, { method: 'POST', body: form });

  if (!response.ok) {
    const raw = await response.text();
    let message = raw;
    try { message = JSON.parse(raw)?.error?.message || raw; } catch (_) {}
    throw new Error(message);
  }

  return response.text();
}

// ─── Main flow ───────────────────────────────────────────────────────────────

transcribeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  hideError();
  transcribeBtn.disabled = true;
  resultWrap.classList.remove('visible');
  progressWrap.classList.add('visible');

  try {
    const rendered     = await extractAudio(selectedFile);
    const SR           = rendered.sampleRate; // 16 000
    const allSamples   = rendered.getChannelData(0);
    const samplesPerChunk = Math.floor(MAX_BYTES / 2); // 2 bytes per 16-bit sample
    const totalChunks  = Math.ceil(allSamples.length / samplesPerChunk);

    let fullText = '';

    for (let i = 0; i < totalChunks; i++) {
      const pct   = 60 + Math.round(((i + 1) / totalChunks) * 36);
      const label = totalChunks > 1
        ? `Transcrevendo parte ${i + 1} de ${totalChunks}…`
        : 'Enviando para transcrição…';

      const start  = i * samplesPerChunk;
      const end    = Math.min((i + 1) * samplesPerChunk, allSamples.length);
      const chunk  = allSamples.slice(start, end);
      const wav    = encodeWAV(chunk, SR);

      setProgress(pct, label, `Parte ${i + 1}: ${fmt(wav.size)}`);

      const part = await transcribeChunk(wav, i, totalChunks);
      fullText += (fullText ? ' ' : '') + part.trim();
    }

    setProgress(100, 'Concluído!', '');

    setTimeout(() => {
      progressWrap.classList.remove('visible');
      resultBox.textContent = fullText;
      const words = fullText.split(/\s+/).filter(Boolean).length;
      wordCount.textContent = `${words} palavras · ${fullText.length} caracteres`;
      resultWrap.classList.add('visible');
      transcribeBtn.disabled = false;
    }, 500);

  } catch (err) {
    progressWrap.classList.remove('visible');
    showError('Erro: ' + err.message);
    transcribeBtn.disabled = false;
  }
});

// ─── Event listeners ─────────────────────────────────────────────────────────

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => setFile(e.target.files[0]));

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  setFile(e.dataTransfer.files[0]);
});

removeBtn.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.remove('visible');
  transcribeBtn.disabled = true;
  resultWrap.classList.remove('visible');
  hideError();
});

copyBtn.addEventListener('click', () => {
  navigator.clipboard.writeText(resultBox.textContent).then(() => {
    copyBtn.textContent = 'Copiado ✓';
    setTimeout(() => (copyBtn.textContent = 'Copiar texto'), 2_000);
  });
});
