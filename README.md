# Fieldwise — Weather-aware crop planning

Fieldwise combines a farmer-entered soil test, a location-based weather forecast, a Python crop-ranking model, and historical yield references. It is a learning project and decision-support prototype, not a substitute for local agronomy advice.

## Stack

- **Frontend:** HTML, CSS, and JavaScript served by Spring Boot.
- **Backend:** Java 25 (LTS) and Spring Boot 3.5.16 REST API.
- **Database:** MySQL 8.4. The API creates/updates the `recommendation_history` table and saves recommendation inputs, forecast snapshots, and model results.
- **Machine learning:** Python 3.13, scikit-learn Random Forest for crop ranking, and Extra Trees regression for historical yield benchmarks.
- **Weather:** The browser calls Open-Meteo geocoding and forecast APIs directly so free Render services do not share weather requests through a common outbound IP.
- **Local runtime:** Docker Compose.

## Run on Windows

1. Install and start Docker Desktop. Wait for the Docker engine to show that it is running.
2. In VS Code, open this project folder.
3. Open the VS Code terminal (Terminal → New Terminal) and run:

   ```powershell
   .\run.ps1
   ```

4. Wait for the first build and model training to finish, then open [http://localhost:8081](http://localhost:8081).
5. Stop the services with `Ctrl+C`. Restart later with `docker compose up`.

The first build downloads Java/Python dependencies, trains the two models, and initializes MySQL. Docker Compose uses local development-only database passwords by default; do not reuse them outside your computer. To override them, copy `.env.example` to `.env`, edit the values, then run `docker compose up --build`.

## Deploy to Render

The root `render.yaml` Blueprint deploys the Java API, Python model service, and a PostgreSQL database in Singapore. It uses Render's free web-service and database plans for a demo. Free web services can sleep when idle, and Render's free PostgreSQL database expires after 30 days; use a paid database plan for long-lived history. The public model service requires a generated shared token, which Render supplies through an environment group.

To deploy, push this project to a GitHub repository, connect that repository to Render, and create a Blueprint from the repository's `render.yaml`. Render will build both Docker services and wire the database credentials and model-service token without storing secrets in Git. The app URL will be the `fieldwise-crop-planner` web service URL. See [Render Blueprints](https://render.com/docs/infrastructure-as-code) and [free instance limits](https://render.com/docs/free).

Useful local URLs:

- App and API: [http://localhost:8081](http://localhost:8081)
- Spring health: [http://localhost:8081/actuator/health](http://localhost:8081/actuator/health)
- MySQL (for a local database client): `127.0.0.1:3308`, database `fieldwise`.
- ML health (inside Compose network): `http://ml-service:8001/health`
- Recent recommendation API: [http://localhost:8080/api/history](http://localhost:8080/api/history)

## Project layout

```text
frontend/                 HTML, CSS, browser JavaScript
backend/                  Spring Boot API and MySQL persistence
ml-service/app/            Model training and FastAPI inference service
ml-service/data/raw/       Bundled public training datasets
compose.yaml               MySQL + API + ML service orchestration
run.ps1                    Windows startup script
```

The earlier Flask prototype files (`app.py`, `recommendation.py`, `weather_service.py`, `static/`, and `templates/`) are retained for reference only. The active application is the Spring Boot, MySQL, and Python ML stack described above.

## Recommendation model and data limits

The crop classifier is trained from the public Crop Recommendation dataset. It uses N, P, K, pH, temperature, and humidity. The form also captures season and soil texture, but the public classifier dataset does not include those fields. The next-seven-day rain total is not compared with the dataset's crop-cycle rainfall field because those measurements do not describe the same time window. The returned score is the model's relative Random Forest vote share, not a calibrated probability.

The yield estimator is trained from district-level Indian crop production data for 1997–2015. It predicts historical tonnes per hectare for the selected state, crop, and season, then scales that benchmark by the entered area. It only returns an estimate when all three categories have matching source records. Historical averages do not account for this year's weather, seed, irrigation, management, or field conditions; the app displays no estimate when a match is unavailable.

The project exposes holdout metrics from training in each API response, but the datasets and models have not been validated for a particular district or farm. Treat the crop shortlist as an exploratory ranking and verify decisions with local agricultural extension services.

The current historical-yield model's temporal holdout mean absolute error is 22.642 tonnes per hectare for 2013–2015. That is high; the yield output is included as a project demonstration and should not be used for operational planting or financial decisions. The app displays this validation result with each recommendation.

Data sources:

- Crop Recommendation dataset: [Atharva Ingle's Kaggle dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset), mirrored as a CSV in this repository's `ml-service/data/raw/` folder.
- Indian district-wise crop production: [data.gov.in dataset](https://www.data.gov.in/resource/district-wise-season-wise-crop-production-statistics-1997), also mirrored in `ml-service/data/raw/`.
- Weather forecast: [Open-Meteo](https://open-meteo.com/).

## API overview

- `GET /api/weather?location=Hyderabad&state=Telangana` — server-side weather lookup for API clients; the browser UI calls Open-Meteo directly.
- `POST /api/recommend` — request model rankings; inputs and results are persisted to MySQL.
- `GET /api/history` — return the latest 20 recommendations.
- `GET /actuator/health` — check Spring Boot health.

To retrain the models locally:

```powershell
python -m venv ml-service/.venv
.\ml-service\.venv\Scripts\python -m pip install -r ml-service\requirements.txt
Push-Location ml-service
.\.venv\Scripts\python -m app.train
Pop-Location
```

The trained artifacts are generated locally and excluded from version control; Docker builds them from the included CSV files.
