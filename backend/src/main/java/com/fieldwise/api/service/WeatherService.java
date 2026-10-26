package com.fieldwise.api.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class WeatherService {
    private static final String GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";
    private static final String FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
    private final RestClient client = RestClient.builder()
            .defaultHeader("User-Agent", "FieldwiseCropAdvisor/1.0")
            .build();

    public Map<String, Object> getWeather(String location, String state) {
        String query = state == null || state.isBlank() || "Other".equalsIgnoreCase(state)
                ? location + ", India"
                : location + ", " + state + ", India";
        try {
            URI geocodingUri = UriComponentsBuilder.fromUriString(GEOCODING_URL)
                    .queryParam("name", query)
                    .queryParam("count", 1)
                    .queryParam("language", "en")
                    .queryParam("countryCode", "IN")
                    .build().encode().toUri();
            JsonNode geocoding = client.get().uri(geocodingUri).retrieve().body(JsonNode.class);
            JsonNode place = geocoding == null ? null : geocoding.path("results").path(0);
            if (place == null || place.isMissingNode() || place.isNull()) {
                throw new WeatherLookupException("We could not find that place in India. Try a nearby city or district name.");
            }

            double latitude = place.path("latitude").asDouble();
            double longitude = place.path("longitude").asDouble();
            return fetchForecast(
                    valueOr(text(place, "name"), location),
                    valueOr(text(place, "admin1"), state),
                    valueOr(text(place, "country"), "India"),
                    latitude,
                    longitude
            );
        } catch (WeatherLookupException exception) {
            throw exception;
        } catch (RestClientException exception) {
            throw new WeatherLookupException("Weather data could not be reached. Check your connection and try again.", exception);
        }
    }

    public Map<String, Object> getWeather(String location, String state, double latitude, double longitude) {
        if (!Double.isFinite(latitude) || latitude < -90 || latitude > 90
                || !Double.isFinite(longitude) || longitude < -180 || longitude > 180) {
            throw new WeatherLookupException("Your browser returned invalid location coordinates. Try entering your city manually.");
        }
        String label = location == null || location.isBlank() ? "Current location" : location.strip();
        return fetchForecast(label, state, "India", latitude, longitude);
    }

    private Map<String, Object> fetchForecast(String locationName, String admin1, String country,
                                               double latitude, double longitude) {
        try {
            URI forecastUri = UriComponentsBuilder.fromUriString(FORECAST_URL)
                    .queryParam("latitude", latitude)
                    .queryParam("longitude", longitude)
                    .queryParam("current", "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m")
                    .queryParam("daily", "temperature_2m_max,temperature_2m_min,precipitation_sum")
                    .queryParam("forecast_days", 7)
                    .queryParam("timezone", "auto")
                    .build().encode().toUri();
            JsonNode forecast = client.get().uri(forecastUri).retrieve().body(JsonNode.class);
            if (forecast == null) {
                throw new WeatherLookupException("Weather data could not be reached. Check your connection and try again.");
            }
            return toWeatherResponse(forecast, locationName, admin1, country, latitude, longitude);
        } catch (WeatherLookupException exception) {
            throw exception;
        } catch (RestClientException exception) {
            throw new WeatherLookupException("Weather data could not be reached. Check your connection and try again.", exception);
        }
    }

    private Map<String, Object> toWeatherResponse(JsonNode forecast, String locationName, String admin1,
                                                   String country, double latitude, double longitude) {
        JsonNode current = forecast.path("current");
        JsonNode daily = forecast.path("daily");
        List<Map<String, Object>> dailyRows = new ArrayList<>();
        JsonNode days = daily.path("time");
        JsonNode rain = daily.path("precipitation_sum");
        JsonNode maxTemps = daily.path("temperature_2m_max");
        JsonNode minTemps = daily.path("temperature_2m_min");
        int count = Math.min(Math.min(days.size(), rain.size()), Math.min(maxTemps.size(), minTemps.size()));
        for (int index = 0; index < count; index++) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", days.get(index).asText());
            row.put("rainMm", rounded(rain.get(index), 1));
            row.put("maxTempC", rounded(maxTemps.get(index), 1));
            row.put("minTempC", rounded(minTemps.get(index), 1));
            dailyRows.add(row);
        }

        Map<String, Object> location = new LinkedHashMap<>();
        location.put("name", locationName);
        location.put("admin1", admin1);
        location.put("country", country);
        location.put("latitude", latitude);
        location.put("longitude", longitude);

        Map<String, Object> currentData = new LinkedHashMap<>();
        currentData.put("temperatureC", rounded(current.path("temperature_2m"), 1));
        currentData.put("humidityPct", rounded(current.path("relative_humidity_2m"), 0));
        currentData.put("precipitationMm", rounded(current.path("precipitation"), 1));
        currentData.put("windKmh", rounded(current.path("wind_speed_10m"), 1));

        Double totalRain = sum(rain);
        Double maximum = extreme(maxTemps, true);
        Double minimum = extreme(minTemps, false);
        Map<String, Object> nextDays = new LinkedHashMap<>();
        nextDays.put("precipitationMm", totalRain == null ? null : round(totalRain, 1));
        nextDays.put("maxTempC", maximum == null ? null : round(maximum, 1));
        nextDays.put("minTempC", minimum == null ? null : round(minimum, 1));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("location", location);
        result.put("updatedAt", text(current, "time"));
        result.put("current", currentData);
        result.put("next7Days", nextDays);
        result.put("daily", dailyRows);
        result.put("timezone", text(forecast, "timezone"));
        return result;
    }

    private static Double rounded(JsonNode node, int digits) {
        return node != null && node.isNumber() ? round(node.asDouble(), digits) : null;
    }

    private static Double sum(JsonNode values) {
        if (values == null || !values.isArray()) return null;
        double total = 0;
        for (JsonNode value : values) {
            if (value.isNumber()) total += value.asDouble();
        }
        return total;
    }

    private static Double extreme(JsonNode values, boolean maximum) {
        if (values == null || !values.isArray()) return null;
        Double result = null;
        for (JsonNode value : values) {
            if (value.isNumber()) {
                result = result == null ? value.asDouble()
                        : maximum ? Math.max(result, value.asDouble()) : Math.min(result, value.asDouble());
            }
        }
        return result;
    }

    private static double round(double value, int digits) {
        double factor = Math.pow(10, digits);
        return Math.round(value * factor) / factor;
    }

    private static String text(JsonNode node, String name) {
        JsonNode value = node.path(name);
        return value.isMissingNode() || value.isNull() ? "" : value.asText("");
    }

    private static String valueOr(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
