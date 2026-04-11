// ── STATE ──────────────────────────────────────────────────────────────────
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? `http://${window.location.host}`
  : window.location.origin;
let sessionId = null;
let streaming = false;
let currentBubble = null;
let currentBubbleText = '';

// ── INIT ───────────────────────────────────────────────────────────────────
async function init() {
  // Restore session from localStorage if available, otherwise create a new one
  const stored = localStorage.getItem('tripzy_session_id');
  if (stored) {
    sessionId = stored;
  } else {
    await createNewSession();
    return;
  }
  // Always show the welcome message on page load (DOM is cleared on refresh)
  addWelcomeMessage();
}

async function createNewSession() {
  const MAX_RETRIES = 5;
  const RETRY_DELAY_MS = 3000;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(`${API}/session`, { method: 'POST' });
      const data = await res.json();
      sessionId = data.session_id;
      localStorage.setItem('tripzy_session_id', sessionId);
      addWelcomeMessage();
      return;
    } catch (err) {
      console.warn(`Init attempt ${attempt}/${MAX_RETRIES} failed:`, err);
      if (attempt < MAX_RETRIES) {
        addStatusMessage(`⏳ Connecting to server… (attempt ${attempt}/${MAX_RETRIES})`);
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
      } else {
        addStatusMessage('⚠️ Could not connect to server. Please refresh the page.');
      }
    }
  }
}

function addWelcomeMessage() {
  addAIMessage(
    "Hello! I'm your AI Travel Agent powered by a multi-agent system. 🌍\n\n" +
    "Tell me about your dream trip — where would you like to go, and when? " +
    "I'll search flights, hotels, check the weather, and create a complete itinerary for you!\n\n" +
    "*Example: \"I want to take a family trip to Bali in June for 7 days, budget $3000\"*"
  );
}

// ── SEND MESSAGE ───────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('input');
  const message = input.value.trim();
  if (!message || streaming) return;

  input.value = '';
  autoResize(input);

  addUserMessage(message);
  setAgentStatus('requirements', 'running', 'Extracting info...');

  // If session was lost (server restart), create a fresh one before sending
  if (!sessionId) {
    await createNewSession();
    if (!sessionId) { finishStreaming(); return; }
  }

  streaming = true;
  document.getElementById('send-btn').disabled = true;

  // Start a new AI bubble for streaming
  currentBubble = null;
  currentBubbleText = '';

  let res;
  try {
    res = await fetch(`${API}/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
  } catch (err) {
    addStatusMessage('⚠️ Connection lost. Please check your network and try again.');
    finishStreaming();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep incomplete line

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const raw = line.slice(6).trim();
      if (raw === '[DONE]') {
        finishStreaming();
        break;
      }
      try {
        handleEvent(JSON.parse(raw));
      } catch (e) {
        // ignore parse errors
      }
    }
  }
}

// ── EVENT HANDLER ──────────────────────────────────────────────────────────
function handleEvent(event) {
  switch (event.type) {

    case 'text': {
      if (!currentBubble) {
        currentBubble = createStreamingBubble();
      }
      currentBubbleText += event.content;
      currentBubble.innerHTML = renderMarkdown(currentBubbleText);
      scrollToBottom();
      break;
    }

    case 'status': {
      addStatusMessage(event.message);
      setAgentStatus('requirements', 'done', 'Done');
      break;
    }

    case 'dto_update': {
      updateTripSummary(event.data);
      setAgentStatus('requirements', 'done', 'DTO updated');
      break;
    }

    case 'agent_status': {
      const statusMap = { flight: 'flight', hotel: 'hotel', climate: 'climate', planning: 'planning' };
      if (statusMap[event.agent]) {
        const labelMap = {
          flight: 'Searching flights...',
          hotel: 'Searching hotels...',
          climate: 'Analyzing weather...',
          planning: 'Creating itinerary...',
        };
        setAgentStatus(event.agent, event.status, labelMap[event.agent] || 'Running...');
      }
      break;
    }

    case 'agent_result': {
      const { agent, status, data } = event;
      if (agent === 'flight' && data && data.top_flights) {
        const f = data.top_flights[0];
        setAgentStatus('flight', 'done', 'Done', f ? `${f.airline} · $${f.price_per_person}/person` : null);
      } else if (agent === 'hotel' && data && data.top_hotels) {
        const h = data.top_hotels[0];
        setAgentStatus('hotel', 'done', 'Done', h ? `${h.name} · $${h.price_per_night}/night` : null);
      } else if (agent === 'climate' && data && data.overall_verdict) {
        setAgentStatus('climate', 'done', 'Done', data.overall_verdict);
      } else if (agent === 'planning') {
        setAgentStatus('planning', 'done', 'Plan ready');
      } else {
        setAgentStatus(agent, status === 'done' ? 'done' : 'error', status);
      }
      break;
    }

    case 'plan_start': {
      // Ensure we create a new bubble for the plan
      if (currentBubble) {
        currentBubble = null;
        currentBubbleText = '';
      }
      break;
    }

    case 'plan_end': {
      if (currentBubble) {
        currentBubble = null;
        currentBubbleText = '';
      }
      break;
    }

    case 'confirm_prompt': {
      addConfirmPrompt(event.message);
      break;
    }

    case 'booking_confirmation': {
      addBookingCard(event.data);
      break;
    }

    case 'error': {
      addStatusMessage('⚠️ ' + (event.message || 'An error occurred'));
      break;
    }
  }
}

function finishStreaming() {
  streaming = false;
  currentBubble = null;
  currentBubbleText = '';
  document.getElementById('send-btn').disabled = false;
}

// ── UI HELPERS ─────────────────────────────────────────────────────────────
function addUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'msg-row user';
  row.innerHTML = `
    <div class="avatar user">👤</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  document.getElementById('messages').appendChild(row);
  scrollToBottom();
}

function addAIMessage(text) {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = renderMarkdown(text);
  row.innerHTML = `<div class="avatar ai">🤖</div>`;
  row.appendChild(bubble);
  document.getElementById('messages').appendChild(row);
  scrollToBottom();
  return bubble;
}

function createStreamingBubble() {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  row.innerHTML = `<div class="avatar ai">🤖</div>`;
  row.appendChild(bubble);
  document.getElementById('messages').appendChild(row);
  scrollToBottom();
  return bubble;
}

function addStatusMessage(text) {
  const el = document.createElement('div');
  el.className = 'status-msg';
  el.innerHTML = renderMarkdown(text);
  document.getElementById('messages').appendChild(el);
  scrollToBottom();
}

function addConfirmPrompt(text) {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  row.innerHTML = `
    <div class="avatar ai">🤖</div>
    <div class="bubble">
      <div class="confirm-prompt">
        <p>${renderMarkdown(text)}</p>
        <button class="confirm-btn" onclick="quickConfirm()">✅ Yes, Book My Trip!</button>
      </div>
    </div>
  `;
  document.getElementById('messages').appendChild(row);
  scrollToBottom();
}

function addBookingCard(data) {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  row.innerHTML = `
    <div class="avatar ai">🤖</div>
    <div class="bubble">
      <div class="booking-card">
        <h3>🎉 Booking Confirmed!</h3>
        <div class="booking-detail"><span class="key">Destination</span><span class="val">${data.destination || '—'}</span></div>
        <div class="booking-detail"><span class="key">Dates</span><span class="val">${data.dates || '—'}</span></div>
        <div class="booking-detail"><span class="key">Travelers</span><span class="val">${data.travelers || '—'}</span></div>
        <div class="booking-detail"><span class="key">Flight Ref</span><span class="val">${data.flight?.booking_reference || '—'}</span></div>
        <div class="booking-detail"><span class="key">Hotel Ref</span><span class="val">${data.hotel?.booking_reference || '—'}</span></div>
      </div>
    </div>
  `;
  document.getElementById('messages').appendChild(row);
  scrollToBottom();
}

function quickConfirm() {
  document.getElementById('input').value = 'Yes, book it!';
  sendMessage();
}

// ── AGENT STATUS ───────────────────────────────────────────────────────────
function setAgentStatus(agent, state, statusText, summary = null) {
  const card = document.getElementById(`agent-${agent}`);
  const statusEl = document.getElementById(`${agent}-status`);
  const summaryEl = document.getElementById(`${agent}-summary`);

  if (!card) return;
  card.className = `agent-card ${state}`;
  if (statusEl) statusEl.textContent = statusText;
  if (summaryEl && summary) {
    summaryEl.textContent = summary;
    summaryEl.style.display = 'block';
  }
}

// ── TRIP SUMMARY SIDEBAR ───────────────────────────────────────────────────
function updateTripSummary(dto) {
  const set = (id, val, fallback = 'Not set') => {
    const el = document.getElementById(id);
    if (!el) return;
    if (val) {
      el.textContent = val;
      el.className = 'value filled';
    } else {
      el.textContent = fallback;
      el.className = 'value empty';
    }
  };

  set('f-dest', dto.destination);
  set('f-origin', dto.origin);

  if (dto.start_date && dto.end_date) {
    set('f-dates', `${dto.start_date} → ${dto.end_date}`);
  } else if (dto.start_date) {
    set('f-dates', `From ${dto.start_date}`);
  } else {
    set('f-dates', null);
  }

  const t = dto.travelers;
  const travStr = `${t.adults} adult${t.adults !== 1 ? 's' : ''}` +
    (t.kids > 0 ? `, ${t.kids} kid${t.kids !== 1 ? 's' : ''}` : '');
  set('f-travelers', travStr, '1 adult');

  if (dto.budget?.total) {
    set('f-budget', `${dto.budget.total.toLocaleString()} ${dto.budget.currency || 'USD'}`);
  } else {
    set('f-budget', null);
  }

  set('f-purpose', dto.purpose ? dto.purpose.charAt(0).toUpperCase() + dto.purpose.slice(1) : null);
  set('f-hotel', dto.preferences?.hotel_type
    ? dto.preferences.hotel_type.charAt(0).toUpperCase() + dto.preferences.hotel_type.slice(1)
    : null);
}

// ── RESET ──────────────────────────────────────────────────────────────────
async function resetSession() {
  if (sessionId) {
    await fetch(`${API}/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
  }
  sessionId = null;
  localStorage.removeItem('tripzy_session_id');
  streaming = false;
  currentBubble = null;
  currentBubbleText = '';

  document.getElementById('messages').innerHTML = '';
  document.getElementById('input').value = '';

  // Reset agents
  ['requirements', 'flight', 'hotel', 'climate', 'planning'].forEach(a => {
    setAgentStatus(a, 'idle', a === 'requirements' ? 'Listening...' : 'Waiting');
    const sum = document.getElementById(`${a}-summary`);
    if (sum) { sum.textContent = ''; sum.style.display = 'none'; }
  });

  // Reset trip summary
  ['f-dest','f-origin','f-dates','f-budget','f-purpose','f-hotel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.textContent = 'Not set'; el.className = 'value empty'; }
  });
  const travelers = document.getElementById('f-travelers');
  if (travelers) { travelers.textContent = '1 adult'; travelers.className = 'value filled'; }

  await createNewSession();
}

// ── MARKDOWN RENDERER (lightweight) ───────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // H1
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // H2
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  // H3
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  // HR
  html = html.replace(/^---$/gm, '<hr>');
  // Bullet lists
  html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  // Numbered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // Paragraphs (double newline)
  html = html.replace(/\n\n/g, '</p><p>');
  // Single newlines
  html = html.replace(/\n/g, '<br>');

  return `<p>${html}</p>`;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── INPUT HELPERS ──────────────────────────────────────────────────────────
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
  const el = document.getElementById('messages');
  el.scrollTop = el.scrollHeight;
}

// ── VOICE INPUT ────────────────────────────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window['webkitSpeechRecognition'];
let recognition = null;
let isRecording = false;

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    const btn = document.getElementById('mic-btn');
    btn.classList.add('recording');
    btn.title = 'Stop recording';
  };

  recognition.onresult = (e) => {
    const transcript = Array.from(e.results)
      .map(r => r[0].transcript)
      .join('');
    document.getElementById('input').value = transcript;
    autoResize(document.getElementById('input'));
  };

  recognition.onerror = (e) => {
    console.warn('Speech recognition error:', e.error);
    stopRecording();
  };

  recognition.onend = () => {
    setTimeout(stopRecording, 2000);
  };
} else {
  // Hide mic button if browser doesn't support it
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('mic-btn');
    if (btn) btn.style.display = 'none';
  });
}

function toggleVoiceInput() {
  if (!recognition) return;
  if (isRecording) {
    recognition.stop();
  } else {
    document.getElementById('input').value = '';
    recognition.start();
  }
}

function stopRecording() {
  isRecording = false;
  const btn = document.getElementById('mic-btn');
  btn.classList.remove('recording');
  btn.title = 'Voice input';
}

// ── WHATSAPP MODAL ─────────────────────────────────────────────────────────
let waQrRendered = false;

async function openWhatsAppModal() {
  document.getElementById('wa-overlay').classList.add('open');

  if (waQrRendered) return; // generate only once
  waQrRendered = true;

  let phone = '+14155238886'; // Twilio sandbox default
  try {
    const res = await fetch(`${API}/whatsapp/config`);
    const data = await res.json();
    if (data.phone) phone = data.phone;
  } catch (_) { /* backend may not be reachable */ }

  const e164 = phone.replace(/\D/g, '');
  const waUrl = `https://wa.me/${e164}?text=Hello%20Tripzy!%20I%27d%20like%20to%20plan%20a%20trip.`;

  document.getElementById('wa-number-display').textContent = phone;
  document.getElementById('wa-direct-link').href = waUrl;

  const container = document.getElementById('wa-qr-canvas');
  container.innerHTML = '';
  new QRCode(container, {
    text: waUrl,
    width: 200,
    height: 200,
    colorDark: '#000000',
    colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.M,
  });
}

function closeWhatsAppModal() {
  document.getElementById('wa-overlay').classList.remove('open');
}

function closeWAModalOnBg(e) {
  if (e.target === document.getElementById('wa-overlay')) closeWhatsAppModal();
}


// ── START ──────────────────────────────────────────────────────────────────
init();
