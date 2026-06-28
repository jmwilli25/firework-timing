const els = {
  fileInput: document.getElementById("plan-file"),
  fullscreenBtn: document.getElementById("fullscreen-btn"),
  countdown: document.getElementById("countdown"),
  calloutPlatform: document.getElementById("callout-platform"),
  calloutFirework: document.getElementById("callout-firework"),
  delayValue: document.getElementById("delay-value"),
  delayMinus: document.getElementById("delay-minus"),
  delayPlus: document.getElementById("delay-plus"),
  startBtn: document.getElementById("start-btn"),
  pauseBtn: document.getElementById("pause-btn"),
  resumeBtn: document.getElementById("resume-btn"),
  resetBtn: document.getElementById("reset-btn"),
  dudConfirm: document.getElementById("dud-confirm"),
  dudBtn: document.getElementById("dud-btn"),
  stationTableBody: document.querySelector("#station-table tbody"),
  message: document.getElementById("message"),
};

const state = {
  loadedPlan: null,
  sequence: [],
  runtimeEvents: [],
  delaySeconds: 5,
  started: false,
  paused: false,
  startEpochMs: 0,
  pauseElapsedSeconds: 0,
  tickerId: null,
  nextIndex: 0,
  lastCalledIndex: -1,
};

function setMessage(text) {
  els.message.textContent = text;
}

function toFixedTenths(value) {
  return (Math.round(value * 10) / 10).toFixed(1);
}

function renderDelay() {
  els.delayValue.textContent = toFixedTenths(state.delaySeconds);
}

function parsePlan(planObject) {
  if (!planObject || !Array.isArray(planObject.stations) || !Array.isArray(planObject.events)) {
    throw new Error("Invalid plan JSON shape.");
  }

  const sequence = planObject.events.map((event) => ({
    station_id: event.station_id,
    firework_name: event.firework_name,
    duration_seconds: Number(event.duration_seconds),
    firework_id: event.firework_id,
  }));

  if (sequence.length === 0) {
    throw new Error("Plan has no events.");
  }

  return {
    stations: planObject.stations,
    sequence,
    delay_seconds: Number(planObject.delay_seconds || 5),
  };
}

function renderStationTable(stations) {
  els.stationTableBody.innerHTML = "";
  for (const station of stations) {
    const row = document.createElement("tr");

    const fwList = station.fireworks
      .map((firework) => `${firework.name} (${firework.duration_seconds}s)`)
      .join(", ");

    row.innerHTML = `
      <td>${station.station_id}</td>
      <td>${station.total_seconds}</td>
      <td>${fwList}</td>
    `;
    els.stationTableBody.appendChild(row);
  }
}

function rebuildRuntimeEvents(startIndex, anchorSeconds, immediateFirstCall) {
  if (!state.sequence.length) {
    return;
  }

  for (let i = startIndex; i < state.sequence.length; i += 1) {
    const item = state.sequence[i];

    let callTime;
    if (i === startIndex) {
      if (immediateFirstCall) {
        callTime = anchorSeconds;
      } else if (i === 0) {
        callTime = 0;
      } else {
        const previous = state.runtimeEvents[i - 1];
        callTime = Math.max(anchorSeconds, previous.expected_end_seconds - state.delaySeconds);
      }
    } else {
      const previous = state.runtimeEvents[i - 1];
      callTime = previous.expected_end_seconds - state.delaySeconds;
    }

    const expectedBurst = callTime + state.delaySeconds;
    const expectedEnd = expectedBurst + item.duration_seconds;

    state.runtimeEvents[i] = {
      ...item,
      call_time_seconds: callTime,
      expected_burst_seconds: expectedBurst,
      expected_end_seconds: expectedEnd,
      status: state.runtimeEvents[i]?.status || "pending",
    };
  }
}

function initializeRuntimeEvents() {
  state.runtimeEvents = [];
  rebuildRuntimeEvents(0, 0, false);
  state.nextIndex = 0;
  state.lastCalledIndex = -1;
}

function getElapsedSeconds() {
  if (!state.started) {
    return 0;
  }

  if (state.paused) {
    return state.pauseElapsedSeconds;
  }

  return (performance.now() - state.startEpochMs) / 1000;
}

function flashCallout() {
  els.calloutPlatform.classList.remove("flash");
  void els.calloutPlatform.offsetWidth;
  els.calloutPlatform.classList.add("flash");
}

function callEvent(index, nowSeconds) {
  const event = state.runtimeEvents[index];
  if (!event) {
    return;
  }

  event.status = "called";
  state.lastCalledIndex = index;
  state.nextIndex = index + 1;

  els.calloutPlatform.textContent = `PLATFORM ${event.station_id}`;
  els.calloutFirework.textContent = event.firework_name;
  flashCallout();

  if (state.nextIndex < state.runtimeEvents.length) {
    rebuildRuntimeEvents(state.nextIndex, nowSeconds, false);
  }
}

function handleDud() {
  if (!els.dudConfirm.checked) {
    setMessage("Check the confirmation box before using DUD.");
    return;
  }

  if (!state.started || state.lastCalledIndex < 0) {
    setMessage("DUD is available after the first platform has been called.");
    els.dudConfirm.checked = false;
    els.dudBtn.disabled = true;
    return;
  }

  if (state.nextIndex >= state.runtimeEvents.length) {
    setMessage("No remaining events to advance to.");
    els.dudConfirm.checked = false;
    els.dudBtn.disabled = true;
    return;
  }

  const nowSeconds = getElapsedSeconds();
  const failedEvent = state.runtimeEvents[state.lastCalledIndex];
  failedEvent.status = "dud";

  rebuildRuntimeEvents(state.nextIndex, nowSeconds, true);
  callEvent(state.nextIndex, nowSeconds);

  els.dudConfirm.checked = false;
  els.dudBtn.disabled = true;
  setMessage(
    `Marked ${failedEvent.firework_name} as dud. Advanced immediately to platform ${state.runtimeEvents[state.lastCalledIndex].station_id}.`
  );
}

function renderCountdown() {
  if (!state.runtimeEvents.length) {
    els.countdown.textContent = "--";
    return;
  }

  const nowSeconds = getElapsedSeconds();

  while (
    state.nextIndex < state.runtimeEvents.length &&
    state.runtimeEvents[state.nextIndex].call_time_seconds <= nowSeconds
  ) {
    callEvent(state.nextIndex, nowSeconds);
  }

  if (state.nextIndex >= state.runtimeEvents.length) {
    els.countdown.textContent = "DONE";
    setMessage("Plan complete.");
    return;
  }

  const nextEvent = state.runtimeEvents[state.nextIndex];
  const remaining = Math.max(0, nextEvent.call_time_seconds - nowSeconds);
  els.countdown.textContent = toFixedTenths(remaining);
  els.calloutPlatform.textContent = `NEXT: PLATFORM ${nextEvent.station_id}`;
  els.calloutFirework.textContent = nextEvent.firework_name;
}

function tick() {
  if (!state.started || state.paused) {
    return;
  }
  renderCountdown();
}

function startTicker() {
  if (state.tickerId) {
    clearInterval(state.tickerId);
  }
  state.tickerId = window.setInterval(tick, 100);
}

function startRun() {
  if (!state.loadedPlan) {
    setMessage("Load a plan JSON first.");
    return;
  }

  state.started = true;
  state.paused = false;
  state.startEpochMs = performance.now();
  state.pauseElapsedSeconds = 0;
  initializeRuntimeEvents();
  startTicker();
  setMessage("Run started.");
  renderCountdown();
}

function pauseRun() {
  if (!state.started || state.paused) {
    return;
  }
  state.pauseElapsedSeconds = getElapsedSeconds();
  state.paused = true;
  setMessage("Paused.");
}

function resumeRun() {
  if (!state.started || !state.paused) {
    return;
  }
  state.startEpochMs = performance.now() - state.pauseElapsedSeconds * 1000;
  state.paused = false;
  setMessage("Resumed.");
}

function resetRun() {
  state.started = false;
  state.paused = false;
  state.pauseElapsedSeconds = 0;
  state.nextIndex = 0;
  state.lastCalledIndex = -1;
  initializeRuntimeEvents();
  renderCountdown();
  setMessage("Reset complete.");
}

function adjustDelay(delta) {
  state.delaySeconds = Math.max(0.5, state.delaySeconds + delta);
  renderDelay();

  if (!state.started) {
    initializeRuntimeEvents();
    return;
  }

  const nowSeconds = getElapsedSeconds();
  const startIndex = state.nextIndex;
  if (startIndex < state.runtimeEvents.length) {
    rebuildRuntimeEvents(startIndex, nowSeconds, false);
  }
  setMessage(`Delay adjusted to ${toFixedTenths(state.delaySeconds)}s.`);
}

async function loadFromFile(file) {
  const text = await file.text();
  const parsed = parsePlan(JSON.parse(text));

  state.loadedPlan = parsed;
  state.sequence = parsed.sequence;
  state.delaySeconds = parsed.delay_seconds > 0 ? parsed.delay_seconds : 5;
  renderDelay();
  renderStationTable(parsed.stations);
  initializeRuntimeEvents();
  renderCountdown();
  setMessage(`Loaded plan with ${state.sequence.length} scheduled events.`);
}

function bindEvents() {
  els.fileInput.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      await loadFromFile(file);
    } catch (error) {
      setMessage(`Failed to load plan: ${error.message}`);
    }
  });

  els.fullscreenBtn.addEventListener("click", () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
      return;
    }
    document.documentElement.requestFullscreen();
  });

  els.startBtn.addEventListener("click", startRun);
  els.pauseBtn.addEventListener("click", pauseRun);
  els.resumeBtn.addEventListener("click", resumeRun);
  els.resetBtn.addEventListener("click", resetRun);
  els.delayMinus.addEventListener("click", () => adjustDelay(-0.2));
  els.delayPlus.addEventListener("click", () => adjustDelay(0.2));

  els.dudConfirm.addEventListener("change", () => {
    els.dudBtn.disabled = !els.dudConfirm.checked;
  });

  els.dudBtn.addEventListener("click", handleDud);
}

renderDelay();
bindEvents();
