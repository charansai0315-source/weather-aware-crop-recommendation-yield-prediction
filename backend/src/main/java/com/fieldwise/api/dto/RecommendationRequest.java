package com.fieldwise.api.dto;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record RecommendationRequest(
        @NotBlank @Size(max = 120) String location,
        @NotBlank @Size(max = 120) String state,
        @NotBlank String season,
        @NotBlank String soilType,
        @NotNull @DecimalMin("0") @DecimalMax("500") Double nitrogen,
        @NotNull @DecimalMin("0") @DecimalMax("500") Double phosphorus,
        @NotNull @DecimalMin("0") @DecimalMax("500") Double potassium,
        @NotNull @DecimalMin("0") @DecimalMax("14") Double ph,
        @NotNull @DecimalMin("0.01") @DecimalMax("100000") Double areaAcres,
        @DecimalMin("0") @DecimalMax("100") Double soilMoisture,
        @NotNull JsonNode weather) {
}
