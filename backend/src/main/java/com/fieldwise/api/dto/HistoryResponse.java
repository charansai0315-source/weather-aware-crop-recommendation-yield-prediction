package com.fieldwise.api.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.time.LocalDateTime;

public record HistoryResponse(
        Long id,
        LocalDateTime createdAt,
        String location,
        String state,
        String season,
        String bestCrop,
        JsonNode result) {
}
