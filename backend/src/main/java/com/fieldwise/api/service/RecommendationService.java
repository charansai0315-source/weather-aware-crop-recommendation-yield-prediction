package com.fieldwise.api.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fieldwise.api.dto.HistoryResponse;
import com.fieldwise.api.dto.RecommendationRequest;
import com.fieldwise.api.entity.RecommendationRecord;
import com.fieldwise.api.repository.RecommendationRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class RecommendationService {
    private final HttpClient mlClient;
    private final String mlServiceUrl;
    private final String mlServiceToken;
    private final RecommendationRepository repository;
    private final ObjectMapper objectMapper;

    public RecommendationService(@Value("${fieldwise.ml.base-url}") String mlServiceUrl,
                                 @Value("${fieldwise.ml.api-token:}") String mlServiceToken,
                                 RecommendationRepository repository,
                                 ObjectMapper objectMapper) {
        this.mlClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(90))
                .build();
        this.mlServiceUrl = mlServiceUrl.replaceAll("/+$", "");
        this.mlServiceToken = mlServiceToken == null ? "" : mlServiceToken.strip();
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> recommend(RecommendationRequest request) {
        JsonNode current = request.weather().path("current");
        JsonNode next7Days = request.weather().path("next7Days");
        Map<String, Object> modelInput = new LinkedHashMap<>();
        modelInput.put("location", request.location());
        modelInput.put("state", request.state());
        modelInput.put("season", request.season());
        modelInput.put("soilType", request.soilType());
        modelInput.put("nitrogen", request.nitrogen());
        modelInput.put("phosphorus", request.phosphorus());
        modelInput.put("potassium", request.potassium());
        modelInput.put("ph", request.ph());
        modelInput.put("areaAcres", request.areaAcres());
        modelInput.put("soilMoisture", request.soilMoisture());
        modelInput.put("temperatureC", numberOrNull(current.path("temperatureC")));
        modelInput.put("humidityPct", numberOrNull(current.path("humidityPct")));
        modelInput.put("rainfallMm", numberOrNull(next7Days.path("precipitationMm")));

        byte[] modelRequest;
        try {
            modelRequest = objectMapper.writeValueAsBytes(modelInput);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Recommendation inputs could not be encoded for the crop model.", exception);
        }

        Map<String, Object> result;
        try {
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder(URI.create(mlServiceUrl + "/recommend"))
                    .header("Content-Type", "application/json")
                    .header("Accept", "application/json");
            if (!mlServiceToken.isEmpty()) {
                requestBuilder.header("X-ML-Service-Token", mlServiceToken);
            }
            HttpRequest httpRequest = requestBuilder
                    .timeout(Duration.ofSeconds(120))
                    .POST(HttpRequest.BodyPublishers.ofByteArray(modelRequest))
                    .build();
            HttpResponse<String> response = mlClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                String message = response.statusCode() >= 400 && response.statusCode() < 500
                        ? "The Python crop model could not use one or more farm or weather values. Review your inputs and try again."
                        : "The Python crop model is temporarily unavailable. Try again shortly.";
                throw new MlServiceException(message,
                        new IllegalStateException("Model service returned HTTP " + response.statusCode()));
            }
            result = objectMapper.readValue(response.body(), new TypeReference<Map<String, Object>>() {});
        } catch (MlServiceException exception) {
            throw exception;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new MlServiceException("The Python crop model request was interrupted. Try again.", exception);
        } catch (IOException | IllegalArgumentException exception) {
            throw new MlServiceException("The Python crop model is unavailable. Start the ML service and try again.", exception);
        }
        if (result == null) {
            throw new MlServiceException("The Python crop model returned an empty response.", new IllegalStateException("Empty ML response"));
        }

        saveRequest(request, result);
        result.put("saved", true);
        return result;
    }

    public List<HistoryResponse> recentHistory() {
        List<HistoryResponse> results = new ArrayList<>();
        for (RecommendationRecord record : repository.findTop20ByOrderByCreatedAtDesc()) {
            try {
                JsonNode result = objectMapper.readTree(record.getResultJson());
                String bestCrop = result.path("recommendations").path(0).path("name").asText("");
                results.add(new HistoryResponse(record.getId(), record.getCreatedAt(), record.getLocation(),
                        record.getState(), record.getSeason(), bestCrop, result));
            } catch (JsonProcessingException exception) {
                throw new IllegalStateException("Saved recommendation JSON could not be read.", exception);
            }
        }
        return results;
    }

    private void saveRequest(RecommendationRequest request, Map<String, Object> result) {
        try {
            RecommendationRecord record = new RecommendationRecord();
            record.setLocation(request.location());
            record.setState(request.state());
            record.setSeason(request.season());
            record.setSoilType(request.soilType());
            record.setAreaAcres(request.areaAcres());
            record.setNitrogen(request.nitrogen());
            record.setPhosphorus(request.phosphorus());
            record.setPotassium(request.potassium());
            record.setSoilPh(request.ph());
            record.setSoilMoisture(request.soilMoisture());
            record.setWeatherJson(objectMapper.writeValueAsString(request.weather()));
            record.setResultJson(objectMapper.writeValueAsString(result));
            repository.save(record);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Recommendation could not be saved.", exception);
        }
    }

    private static Double numberOrNull(JsonNode node) {
        return node != null && node.isNumber() ? node.asDouble() : null;
    }
}
