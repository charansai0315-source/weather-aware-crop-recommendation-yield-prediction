from flask import Flask, jsonify, render_template, request

from recommendation import RecommendationInputError, recommend_crops
from weather_service import WeatherLookupError, get_weather


app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/weather")
def weather():
    location = request.args.get("location", "").strip()
    state = request.args.get("state", "").strip()
    if not location:
        return jsonify(error="Enter a city or district to look up its weather."), 400

    try:
        return jsonify(get_weather(location, state))
    except WeatherLookupError as exc:
        return jsonify(error=str(exc)), 502


@app.post("/api/recommend")
def recommend():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Send the farm details as JSON."), 400

    try:
        result = recommend_crops(payload)
    except RecommendationInputError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
