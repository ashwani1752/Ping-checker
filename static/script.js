// Short helper to get an element by its id
const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------
// Show the result of a ping test (or an error message)
// ------------------------------------------------------------
function showResult(data, isError) {
  const box = $("result");
  box.classList.remove("hidden", "online", "offline", "invalid");

  if (isError) {
    // Validation / server error: hide the detail grid values
    box.classList.add("invalid");
    $("resultMessage").textContent = "⚠ " + data.error;
    ["rHost", "rStatus", "rLatency", "rSent", "rReceived", "rLoss"].forEach(
      (id) => ($(id).textContent = "-")
    );
    return;
  }

  const online = data.status === "Online";
  box.classList.add(online ? "online" : "offline");
  $("resultMessage").textContent = (online ? "✅ " : "❌ ") + data.message;
  $("rHost").textContent = data.host;
  $("rStatus").textContent = data.status;
  $("rLatency").textContent =
    data.response_time !== null ? data.response_time + " ms" : "—";
  $("rSent").textContent = data.packets_sent;
  $("rReceived").textContent = data.packets_received;
  $("rLoss").textContent = data.packet_loss + "%";
}

// ------------------------------------------------------------
// Draw the Online vs Offline doughnut chart on a <canvas>
// ------------------------------------------------------------
function drawChart(online, offline) {
  const canvas = $("statusChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const size = canvas.width;
  const center = size / 2;
  const radius = size / 2 - 24;
  const total = online + offline;

  ctx.clearRect(0, 0, size, size);
  ctx.lineWidth = 28;

  if (total === 0) {
    // No data yet: draw a grey ring
    ctx.beginPath();
    ctx.arc(center, center, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#e2e8f0";
    ctx.stroke();
  } else {
    let start = -Math.PI / 2; // start from the top
    [[online, "#16a34a"], [offline, "#dc2626"]].forEach(([value, color]) => {
      if (value === 0) return;
      const angle = (value / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(center, center, radius, start, start + angle);
      ctx.strokeStyle = color;
      ctx.stroke();
      start += angle;
    });
  }

  // Text in the middle of the doughnut
  ctx.fillStyle = "#0f172a";
  ctx.textAlign = "center";
  ctx.font = "bold 32px Segoe UI, Arial";
  ctx.fillText(total, center, center + 8);
  ctx.fillStyle = "#64748b";
  ctx.font = "14px Segoe UI, Arial";
  ctx.fillText("tests", center, center + 30);
}

// ------------------------------------------------------------
// Fill the "Recent Ping Tests" table (uses textContent = safe from XSS)
// ------------------------------------------------------------
function renderRecent(rows) {
  const body = $("recentBody");
  body.innerHTML = "";

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "muted center";
    td.textContent = "No tests yet.";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const cells = [
      row.host,
      row.tested_at,
      null, // status badge goes here
      row.response_time !== null ? row.response_time + " ms" : "—",
      row.packet_loss + "%",
    ];
    cells.forEach((value, index) => {
      const td = document.createElement("td");
      if (index === 2) {
        const badge = document.createElement("span");
        badge.className = "badge " + (row.status === "Online" ? "badge-online" : "badge-offline");
        badge.textContent = row.status;
        td.appendChild(badge);
      } else {
        td.textContent = value;
      }
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

// ------------------------------------------------------------
// Load dashboard numbers from the server
// ------------------------------------------------------------
async function loadStats() {
  if (!$("sTotal")) return; // not on the dashboard page
  try {
    const response = await fetch("/api/stats");
    const stats = await response.json();
    if (stats.error) return;
    $("sTotal").textContent = stats.total;
    $("sOnline").textContent = stats.online;
    $("sOffline").textContent = stats.offline;
    $("sAvg").textContent = stats.avg_response !== null ? stats.avg_response + " ms" : "—";
    renderRecent(stats.recent);
    drawChart(stats.online, stats.offline);
  } catch (err) {
    console.error("Could not load stats:", err);
  }
}

// ------------------------------------------------------------
// Handle the ping form
// ------------------------------------------------------------
const pingForm = $("pingForm");
if (pingForm) {
  pingForm.addEventListener("submit", async (event) => {
    event.preventDefault(); // stop normal page reload
    const host = $("hostInput").value.trim();
    const button = $("checkBtn");

    if (!host) {
      showResult({ error: "Please enter an IP address or hostname." }, true);
      return;
    }

    button.disabled = true;
    button.textContent = "Checking...";

    try {
      const response = await fetch("/api/ping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: host }),
      });
      const data = await response.json();
      showResult(data, !response.ok);
      if (response.ok) loadStats(); // refresh dashboard
    } catch (err) {
      showResult({ error: "Could not reach the server. Is Flask running?" }, true);
    } finally {
      button.disabled = false;
      button.textContent = "Check Connectivity";
    }
  });
}

// ------------------------------------------------------------
// Ask for confirmation before clearing history
// ------------------------------------------------------------
const clearForm = $("clearForm");
if (clearForm) {
  clearForm.addEventListener("submit", (event) => {
    if (!confirm("Delete all ping history? This cannot be undone.")) {
      event.preventDefault();
    }
  });
}

// Load the dashboard when the page opens
loadStats();
