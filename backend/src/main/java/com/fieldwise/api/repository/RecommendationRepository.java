package com.fieldwise.api.repository;

import com.fieldwise.api.entity.RecommendationRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface RecommendationRepository extends JpaRepository<RecommendationRecord, Long> {
    List<RecommendationRecord> findTop20ByOrderByCreatedAtDesc();
}
