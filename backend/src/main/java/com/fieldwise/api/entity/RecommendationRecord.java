package com.fieldwise.api.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDateTime;
import java.time.ZoneOffset;

@Entity
@Table(name = "recommendation_history")
public class RecommendationRecord {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false, length = 120)
    private String location;

    @Column(nullable = false, length = 120)
    private String state;

    @Column(nullable = false, length = 20)
    private String season;

    @Column(nullable = false, length = 30)
    private String soilType;

    @Column(nullable = false)
    private double areaAcres;

    @Column(nullable = false)
    private double nitrogen;

    @Column(nullable = false)
    private double phosphorus;

    @Column(nullable = false)
    private double potassium;

    @Column(nullable = false)
    private double soilPh;

    private Double soilMoisture;

    @Column(nullable = false, columnDefinition = "text")
    private String weatherJson;

    @Column(nullable = false, columnDefinition = "text")
    private String resultJson;

    @PrePersist
    void setCreatedAt() {
        if (createdAt == null) {
            createdAt = LocalDateTime.now(ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public String getLocation() { return location; }
    public String getState() { return state; }
    public String getSeason() { return season; }
    public String getSoilType() { return soilType; }
    public double getAreaAcres() { return areaAcres; }
    public double getNitrogen() { return nitrogen; }
    public double getPhosphorus() { return phosphorus; }
    public double getPotassium() { return potassium; }
    public double getSoilPh() { return soilPh; }
    public Double getSoilMoisture() { return soilMoisture; }
    public String getWeatherJson() { return weatherJson; }
    public String getResultJson() { return resultJson; }

    public void setLocation(String location) { this.location = location; }
    public void setState(String state) { this.state = state; }
    public void setSeason(String season) { this.season = season; }
    public void setSoilType(String soilType) { this.soilType = soilType; }
    public void setAreaAcres(double areaAcres) { this.areaAcres = areaAcres; }
    public void setNitrogen(double nitrogen) { this.nitrogen = nitrogen; }
    public void setPhosphorus(double phosphorus) { this.phosphorus = phosphorus; }
    public void setPotassium(double potassium) { this.potassium = potassium; }
    public void setSoilPh(double soilPh) { this.soilPh = soilPh; }
    public void setSoilMoisture(Double soilMoisture) { this.soilMoisture = soilMoisture; }
    public void setWeatherJson(String weatherJson) { this.weatherJson = weatherJson; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
}
