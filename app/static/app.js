const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const ingestBtn = document.getElementById("ingest-btn");
const pdfInput = document.getElementById("pdf-input");
const ingestStatus = document.getElementById("ingest-status");

function appendMessage(text, cssClass, meta) {
  const div = document.createElement("div");
  div.className = `msg ${cssClass}`;
  div.textContent = text;
  if (meta) {
    const metaEl = document.createElement("span");
    metaEl.className = "meta";
    metaEl.textContent = meta;
    div.appendChild(metaEl);
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

appendMessage(
  "👋 Hi, I'm your HR support assistant! Ask me anything about leave, payroll, benefits, " +
    "onboarding, or company policies — I'll dig through the HR docs and get you an answer.",
  "bot"
);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  appendMessage(message, "user");
  input.value = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    const cssClass = data.blocked ? "blocked" : "bot";
    let meta = `intent: ${data.intent}`;
    if (data.escalated) meta += ` | escalated to: ${data.escalated_to}`;
    if (data.sources && data.sources.length) {
      meta += ` | sources: ${data.sources.map((s) => s.source).join(", ")}`;
    }
    appendMessage(data.answer, cssClass, meta);
  } catch (err) {
    appendMessage("Something went wrong talking to the server.", "blocked");
  }
});

ingestBtn.addEventListener("click", async () => {
  if (!pdfInput.files.length) {
    ingestStatus.textContent = "Pick at least one PDF first.";
    return;
  }
  const formData = new FormData();
  for (const file of pdfInput.files) formData.append("files", file);

  ingestStatus.textContent = "Ingesting...";
  try {
    const res = await fetch("/api/ingest", { method: "POST", body: formData });
    const data = await res.json();
    ingestStatus.textContent = `Ingested ${data.files_ingested.length} file(s), ${data.chunks_added} chunks.`;
  } catch (err) {
    ingestStatus.textContent = "Ingestion failed.";
  }
});
