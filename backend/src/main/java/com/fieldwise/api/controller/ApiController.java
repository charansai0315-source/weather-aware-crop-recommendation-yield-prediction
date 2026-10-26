package com.fieldwise.api.controller;

import com.fieldwise.api.dto.HistoryResponse;
import com.fieldwise.api.dto.RecommendationRequest;
import com.fieldwise.api.service.RecommendationService;
import com.fieldwise.api.service.WeatherService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
public class ApiController {
    private final WeatherService weatherService;
    private final RecommendationService recommendationService;

    public ApiController(WeatherService weatherService, RecommendationService recommendationService) {
        this.weatherService = weatherService;
        this.recommendationService = recommendationService;
    }

    @GetMapping("/api/weather")
    public Map<String, Object> weather(@RequestParam(required = false) String location,
                                       @RequestParam(defaultValue = "") String state,
                                       @RequestParam(required = false) Double latitude,
                                       @RequestParam(required = false) Double longitude) {
        if ((latitude == null) != (longitude == null)) {
            throw new IllegalArgumentException("Both latitude and longitude are required for current-location weather.");
        }
        if (latitude != null) {
            return weatherService.getWeather(location, state.strip(), latitude, longitude);
        }
        if (location == null || location.isBlank()) {
            throw new IllegalArgumentException("Enter a city or district to look up its weather.");
        }
        return weatherService.getWeather(location.strip(), state.strip());
    }

    @PostMapping("/api/recommend")
    public Map<String, Object> recommend(@Valid @RequestBody RecommendationRequest request) {
        return recommendationService.recommend(request);
    }

    @GetMapping("/api/history")
    public List<HistoryResponse> history() {
        return recommendationService.recentHistory();
    }
}
