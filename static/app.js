const weatherButton = document.getElementById("weather-button");
const weatherMessage = document.getElementById("weather-message");
const weatherCard = document.getElementById("weather-card");
const plannerForm = document.getElementById("planner-form");
const formMessage = document.getElementById("form-message");
const recommendButton = document.getElementById("recommend-button");
const resultsSection = document.getElementById("results-section");
let weatherSnapshot = null;

const byId = (id) => document.getElementById(id);

async function readApiJson(response, appUrl, fallbackMessage) {
  const body = await response.text();
  let data;
  try {
    data = body ? JSON.parse(body) : {};
  } catch {
    const isForbidden = response.status === 403 || body.trim().toLowerCase() === "forbidden.";
    if (isForbidden) {
      throw new Error(`This server blocked the API request (403 Forbidden). Open the running app at ${appUrl} and try again.`);
    }
    if (response.status === 404) {
      throw new Error(`This page is not connected to the Fieldwise API. Open the running app at ${appUrl} and try again.`);
    }
    throw new Error(response.ok
      ? `The server returned an unreadable response. Open the running app at ${appUrl} and try again.`
      : `${fallbackMessage} (HTTP ${response.status}).`);
  }
  if (!response.ok) throw new Error(data.error || `${fallbackMessage} (HTTP ${response.status}).`);
  return data;
}

weatherButton.addEventListener("click", loadWeather);
plannerForm.addEventListener("submit", submitPlan);
byId("sample-button").addEventListener("click", fillExample);
byId("location").addEventListener("input", invalidateWeather);
byId("state").addEventListener("change", invalidateWeather);
plannerForm.querySelectorAll("#soil-type, #season, #nitrogen, #phosphorus, #potassium, #ph, #area, #soil-moisture").forEach((field) => {
  field.addEventListener("input", invalidateResults);
  field.addEventListener("change", invalidateResults);
});

async function loadWeather() {
  const location = byId("location").value.trim();
  const state = byId("state").value;
  weatherMessage.textContent = "";
  weatherCard.classList.add("hidden");
  weatherSnapshot = null;
  resultsSection.classList.add("hidden");

  if (!location) {
    weatherMessage.textContent = "Enter a city or district first.";
    byId("location").focus();
    return false;
  }

  setBusy(weatherButton, true, "Finding forecast…");
  try {
    const params = new URLSearchParams({ location, state });
    const response = await fetch(`/api/weather?${params}`);
    const data = await readApiJson(response, "http://127.0.0.1:5000", "Weather lookup failed");
    weatherSnapshot = data;
    renderWeather(data);
    weatherCard.classList.remove("hidden");
    weatherMessage.textContent = "Forecast loaded for your selected area.";
    weatherMessage.style.color = "#63825a";
    return true;
  } catch (error) {
    weatherMessage.textContent = error.message === "Failed to fetch"
      ? "The app server is offline. Start it with run.ps1, then refresh this page."
      : (error.message || "Could not load the weather right now.");
    weatherMessage.style.color = "#a24b3e";
    return false;
  } finally {
    setBusy(weatherButton, false, "Get local weather");
  }
}

function invalidateWeather() {
  if (!weatherSnapshot) return;
  weatherSnapshot = null;
  weatherCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  weatherMessage.textContent = "Location changed. Load the forecast for this area before continuing.";
  weatherMessage.style.color = "#a24b3e";
}

function invalidateResults() {
  resultsSection.classList.add("hidden");
}

function renderWeather(data) {
  const place = data.location;
  byId("weather-place").textContent = [place.name, place.admin1].filter(Boolean).join(", ");
  byId("weather-temp").textContent = displayNumber(data.current.temperatureC);
  byId("weather-humidity").textContent = displayNumber(data.current.humidityPct, 0);
  byId("weather-wind").textContent = displayNumber(data.current.windKmh);
  byId("weather-rain").textContent = displayNumber(data.next7Days.precipitationMm);
}

async function submitPlan(event) {
  event.preventDefault();
  formMessage.textContent = "";
  formMessage.style.color = "";
  if (!plannerForm.reportValidity()) return;
  if (!weatherSnapshot) {
    setBusy(recommendButton, true, "Getting local weather…");
    const loaded = await loadWeather();
    setBusy(recommendButton, false, "Show crop matches");
    if (!loaded) {
      formMessage.textContent = weatherMessage.textContent || "Could not load weather for this location.";
      return;
    }
  }

  const moistureValue = byId("soil-moisture").value;
  const payload = {
    season: byId("season").value,
    soilType: byId("soil-type").value,
    nitrogen: byId("nitrogen").value,
    phosphorus: byId("phosphorus").value,
    potassium: byId("potassium").value,
    ph: byId("ph").value,
    areaAcres: byId("area").value,
    soilMoisture: moistureValue === "" ? null : moistureValue,
    weather: weatherSnapshot,
  };

  setBusy(recommendButton, true, "Finding best crop…");
  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readApiJson(response, "http://127.0.0.1:5000", "Could not create recommendations");
    renderRecommendations(data);
    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    formMessage.textContent = error.message === "Failed to fetch"
      ? "The app server is offline. Start it with run.ps1, then refresh this page."
      : (error.message || "Could not create recommendations.");
  } finally {
    setBusy(recommendButton, false, "Show crop matches");
  }
}

function renderRecommendations(data) {
  byId("method-badge").textContent = data.method;
  byId("yield-note").textContent = data.yieldNote;
  const list = byId("recommendation-list");
  list.replaceChildren();

  data.recommendations.forEach((crop, index) => {
    const card = document.createElement("article");
    card.className = `recommendation-card${index === 0 ? " best" : ""}`;
    const rank = document.createElement("span");
    rank.className = "rank-label";
    rank.textContent = index === 0 ? "BEST RECOMMENDED CROP" : `OPTION 0${index + 1}`;
    const title = document.createElement("h3");
    title.textContent = crop.name;
    const scoreLine = document.createElement("div");
    scoreLine.className = "score-line";
    const scoreLabel = document.createElement("span");
    scoreLabel.textContent = "Profile fit";
    const score = document.createElement("strong");
    score.textContent = `${crop.suitability}%`;
    scoreLine.append(scoreLabel, score);
    const yieldValue = document.createElement("p");
    yieldValue.className = "yield-number";
    yieldValue.textContent = `${crop.estimatedYieldTonnes} t`;
    const yieldCaption = document.createElement("span");
    yieldCaption.className = "yield-caption";
    yieldCaption.textContent = "rough total for your entered land area";
    const reasons = document.createElement("ul");
    reasons.className = "match-reasons";
    crop.reasons.forEach((reason) => {
      const item = document.createElement("li");
      item.textContent = reason;
      reasons.append(item);
    });
    const note = document.createElement("p");
    note.className = "crop-note";
    note.textContent = crop.note;
    card.append(rank, title, scoreLine, yieldValue, yieldCaption, reasons, note);
    list.append(card);
  });

  const advice = byId("advice-list");
  advice.replaceChildren();
  data.warnings.forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    advice.append(item);
  });
}

function fillExample() {
  weatherSnapshot = null;
  weatherCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  weatherMessage.textContent = "";
  byId("nitrogen").value = "90";
  byId("phosphorus").value = "42";
  byId("potassium").value = "43";
  byId("ph").value = "6.5";
  byId("area").value = "2";
  byId("soil-moisture").value = "";
  byId("location").value = "Hyderabad";
  byId("state").value = "Telangana";
  byId("soil-type").value = "clay";
  byId("season").value = "Kharif";
  formMessage.textContent = "Example details filled. Get local weather to continue.";
  formMessage.style.color = "#63825a";
  byId("location").focus();
}

function displayNumber(value, digits = 1) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(digits);
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  const labelElement = button.querySelector("span:not(.button-icon):not(.arrow)");
  if (labelElement) labelElement.textContent = label;
}
