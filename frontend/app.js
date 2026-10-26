const weatherButton = document.getElementById("weather-button");
const locationButton = document.getElementById("location-button");
const weatherMessage = document.getElementById("weather-message");
const weatherCard = document.getElementById("weather-card");
const plannerForm = document.getElementById("planner-form");
const formMessage = document.getElementById("form-message");
const recommendButton = document.getElementById("recommend-button");
const resultsSection = document.getElementById("results-section");
const runtimeBanner = document.getElementById("runtime-banner");
let weatherSnapshot = null;
let currentCoordinates = null;

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

const GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";
const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";

async function readOpenMeteoJson(url) {
  const response = await fetch(url);
  const body = await response.text();
  let data;
  try {
    data = body ? JSON.parse(body) : {};
  } catch {
    const isForbidden = response.status === 403 || body.trim().toLowerCase() === "forbidden.";
    throw new Error(isForbidden
      ? "Open-Meteo refused this request (403 Forbidden). Try again shortly."
      : `Weather service returned an unreadable response (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    throw new Error(data.reason || data.error || `Weather service request failed (HTTP ${response.status}).`);
  }
  return data;
}

function roundedOrNull(value, digits = 1) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

async function lookupWeather(location, state, coordinates) {
  let place;
  let latitude;
  let longitude;

  if (coordinates) {
    latitude = coordinates.latitude;
    longitude = coordinates.longitude;
    place = {
      name: "Current GPS location",
      admin1: state === "Other" ? "" : state,
      country: "India",
    };
  } else {
    const query = state && state !== "Other" ? `${location}, ${state}, India` : `${location}, India`;
    const params = new URLSearchParams({ name: query, count: "1", language: "en", countryCode: "IN" });
    const geocoding = await readOpenMeteoJson(`${GEOCODING_URL}?${params}`);
    place = geocoding.results?.[0];
    if (!place) {
      throw new Error("We could not find that place in India. Try a nearby city or district name.");
    }
    latitude = place.latitude;
    longitude = place.longitude;
  }

  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    current: "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
    daily: "temperature_2m_max,temperature_2m_min,precipitation_sum",
    forecast_days: "7",
    timezone: "auto",
  });
  const forecast = await readOpenMeteoJson(`${FORECAST_URL}?${params}`);
  const current = forecast.current || {};
  const daily = forecast.daily || {};
  const days = daily.time || [];
  const rain = daily.precipitation_sum || [];
  const maxTemps = daily.temperature_2m_max || [];
  const minTemps = daily.temperature_2m_min || [];
  const rowCount = Math.min(days.length, rain.length, maxTemps.length, minTemps.length);
  const numericRain = rain.filter((value) => typeof value === "number" && Number.isFinite(value));
  const numericMax = maxTemps.filter((value) => typeof value === "number" && Number.isFinite(value));
  const numericMin = minTemps.filter((value) => typeof value === "number" && Number.isFinite(value));

  return {
    location: {
      name: place.name || location || "Current location",
      admin1: place.admin1 || (state === "Other" ? "" : state),
      country: place.country || "India",
      latitude,
      longitude,
    },
    updatedAt: current.time || null,
    current: {
      temperatureC: roundedOrNull(current.temperature_2m),
      humidityPct: roundedOrNull(current.relative_humidity_2m, 0),
      precipitationMm: roundedOrNull(current.precipitation),
      windKmh: roundedOrNull(current.wind_speed_10m),
    },
    next7Days: {
      precipitationMm: numericRain.length ? roundedOrNull(numericRain.reduce((sum, value) => sum + value, 0)) : null,
      maxTempC: numericMax.length ? roundedOrNull(Math.max(...numericMax)) : null,
      minTempC: numericMin.length ? roundedOrNull(Math.min(...numericMin)) : null,
    },
    daily: Array.from({ length: rowCount }, (_, index) => ({
      date: days[index],
      rainMm: roundedOrNull(rain[index]),
      maxTempC: roundedOrNull(maxTemps[index]),
      minTempC: roundedOrNull(minTemps[index]),
    })),
    timezone: forecast.timezone || "",
  };
}

weatherButton.addEventListener("click", loadWeather);
locationButton.addEventListener("click", useCurrentLocation);
plannerForm.addEventListener("submit", submitPlan);
byId("sample-button").addEventListener("click", fillExample);
byId("location").addEventListener("input", () => {
  currentCoordinates = null;
  invalidateWeather();
});
byId("state").addEventListener("change", invalidateWeather);
plannerForm.querySelectorAll("#soil-type, #season, #nitrogen, #phosphorus, #potassium, #ph, #area, #soil-moisture").forEach((field) => {
  field.addEventListener("input", invalidateResults);
  field.addEventListener("change", invalidateResults);
});

if (window.location.protocol === "file:") {
  runtimeBanner.textContent = "You opened the HTML file directly. The styled preview works here, but live weather and crop recommendations need the running app at http://localhost:8081. Start it with run.ps1.";
  runtimeBanner.classList.remove("hidden");
}

async function loadWeather() {
  const location = byId("location").value.trim();
  const state = byId("state").value;
  weatherMessage.textContent = "";
  weatherCard.classList.add("hidden");
  weatherSnapshot = null;
  resultsSection.classList.add("hidden");

  if (window.location.protocol === "file:") {
    weatherMessage.textContent = "Open http://localhost:8081 to load live weather and crop recommendations.";
    weatherMessage.style.color = "#a24b3e";
    return false;
  }

  if (!location && !currentCoordinates) {
    weatherMessage.textContent = "Enter a city or district first.";
    byId("location").focus();
    return false;
  }

  setBusy(weatherButton, true, "Finding forecast…");
  try {
    const data = await lookupWeather(location, state, currentCoordinates);
    weatherSnapshot = data;
    renderWeather(data);
    weatherCard.classList.remove("hidden");
    weatherMessage.textContent = currentCoordinates
      ? "Forecast loaded for your current GPS location."
      : "Forecast loaded for your selected area.";
    weatherMessage.style.color = "#63825a";
    return true;
  } catch (error) {
    weatherMessage.textContent = error.message === "Failed to fetch"
      ? "Could not reach the weather service from this browser. Check your connection and try again."
      : (error.message || "Could not load the weather right now.");
    weatherMessage.style.color = "#a24b3e";
    return false;
  } finally {
    setBusy(weatherButton, false, "Get local weather");
  }
}

function useCurrentLocation() {
  if (window.location.protocol === "file:") {
    weatherMessage.textContent = "Open http://localhost:8081 to use browser location and live weather.";
    weatherMessage.style.color = "#a24b3e";
    return;
  }
  if (!navigator.geolocation) {
    weatherMessage.textContent = "This browser does not support location sharing. Enter your city or district instead.";
    weatherMessage.style.color = "#a24b3e";
    return;
  }

  currentCoordinates = null;
  if (byId("location").value.startsWith("Current GPS location (")) {
    byId("location").value = "";
  }
  weatherSnapshot = null;
  weatherCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  weatherMessage.textContent = "Allow location access in your browser to get weather for your current position.";
  weatherMessage.style.color = "#738078";
  setBusy(locationButton, true, "Finding current location…");
  navigator.geolocation.getCurrentPosition((position) => {
    currentCoordinates = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
    };
    byId("location").value = `Current GPS location (${currentCoordinates.latitude.toFixed(4)}, ${currentCoordinates.longitude.toFixed(4)})`;
    invalidateWeather();
    loadWeather().finally(() => setBusy(locationButton, false, "Use my current location"));
  }, (error) => {
    const messages = {
      1: "Location permission was denied. Allow it in your browser, or enter your city manually.",
      2: "Your current location is unavailable. Check device location services or enter your city manually.",
      3: "Location lookup timed out. Try again or enter your city manually.",
    };
    weatherMessage.textContent = messages[error.code] || "Could not get your location. Enter your city or district manually.";
    weatherMessage.style.color = "#a24b3e";
    setBusy(locationButton, false, "Use my current location");
  }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 });
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
  if (!byId("state").value) {
    formMessage.textContent = "Choose your state or union territory so the system can match historical yield data.";
    byId("state").focus();
    return;
  }
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
    location: byId("location").value.trim(),
    state: byId("state").value,
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
    const data = await readApiJson(response, "http://localhost:8081", "Could not create recommendations");
    renderRecommendations(data);
    resultsSection.classList.remove("hidden");
    formMessage.textContent = data.saved
      ? "Crop matches are ready. This recommendation was saved to the project database."
      : "Crop matches are ready.";
    formMessage.style.color = "#63825a";
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
    scoreLabel.textContent = "Relative model vote share";
    const score = document.createElement("strong");
    score.textContent = `${crop.suitability}%`;
    scoreLine.append(scoreLabel, score);
    const yieldValue = document.createElement("p");
    yieldValue.className = "yield-number";
    yieldValue.textContent = crop.estimatedYieldTonnes == null
      ? "No matched data"
      : `${Number(crop.estimatedYieldTonnes).toFixed(2)} t`;
    const yieldCaption = document.createElement("span");
    yieldCaption.className = "yield-caption";
    yieldCaption.textContent = crop.estimatedYieldTonnes == null
      ? "historical yield is unavailable for this crop, state and season"
      : `historical benchmark · ${Number(crop.yieldTonnesPerHectare).toFixed(2)} t/ha · your entered area`;
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
  currentCoordinates = null;
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
