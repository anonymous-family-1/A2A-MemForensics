type GeocodingResponse = {
  results?: Array<{
    name: string;
    country?: string;
    admin1?: string;
    latitude: number;
    longitude: number;
    timezone: string;
  }>;
};

type ForecastResponse = {
  current?: {
    temperature_2m: number;
    relative_humidity_2m: number;
    apparent_temperature: number;
    weather_code: number;
    wind_speed_10m: number;
  };
  daily?: {
    time: string[];
    weather_code: number[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_probability_max?: Array<number | null>;
  };
  timezone?: string;
};

export interface WeatherData {
  locationName: string;
  timezone: string;
  temperature: number;
  apparentTemperature: number;
  condition: string;
  humidity: number;
  windSpeed: number;
}

interface ForecastDay {
  date: string;
  condition: string;
  maxTemperature: number;
  minTemperature: number;
  precipitationProbability: number | null;
}

const GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search";
const FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast";
export const MAX_FORECAST_DAYS = 16;

function formatLocationName(result: NonNullable<GeocodingResponse["results"]>[number]): string {
  return [result.name, result.admin1, result.country].filter(Boolean).join(", ");
}

function weatherCodeToDescription(code: number): string {
  const descriptions: Record<number, string> = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "rainy",
    63: "rainy",
    65: "heavy rain",
    71: "light snow",
    73: "snowy",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorms",
    96: "thunderstorms",
    99: "severe thunderstorms",
  };

  return descriptions[code] ?? `weather code ${code}`;
}

async function fetchJson<T>(url: URL): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Open-Meteo request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

async function resolveLocation(locationQuery: string) {
  const url = new URL(GEOCODING_ENDPOINT);
  url.searchParams.set("name", locationQuery);
  url.searchParams.set("count", "1");
  url.searchParams.set("language", "en");
  url.searchParams.set("format", "json");

  const payload = await fetchJson<GeocodingResponse>(url);
  const match = payload.results?.[0];
  if (!match) {
    return null;
  }

  return {
    latitude: match.latitude,
    longitude: match.longitude,
    timezone: match.timezone,
    locationName: formatLocationName(match),
  };
}

export async function getWeather(locationQuery: string): Promise<WeatherData | null> {
  const resolved = await resolveLocation(locationQuery);
  if (!resolved) {
    return null;
  }

  const url = new URL(FORECAST_ENDPOINT);
  url.searchParams.set("latitude", String(resolved.latitude));
  url.searchParams.set("longitude", String(resolved.longitude));
  url.searchParams.set(
    "current",
    [
      "temperature_2m",
      "relative_humidity_2m",
      "apparent_temperature",
      "weather_code",
      "wind_speed_10m",
    ].join(",")
  );
  url.searchParams.set("timezone", "auto");

  const forecast = await fetchJson<ForecastResponse>(url);
  if (!forecast.current) {
    return null;
  }

  return {
    locationName: resolved.locationName,
    timezone: forecast.timezone ?? resolved.timezone,
    temperature: forecast.current.temperature_2m,
    apparentTemperature: forecast.current.apparent_temperature,
    condition: weatherCodeToDescription(forecast.current.weather_code),
    humidity: forecast.current.relative_humidity_2m,
    windSpeed: forecast.current.wind_speed_10m,
  };
}

function formatIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function buildForecastRange(days: number): { startDate: string; endDate: string } {
  const safeDays = Math.max(1, Math.min(days, MAX_FORECAST_DAYS));
  const start = new Date();
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + safeDays - 1);

  return {
    startDate: formatIsoDate(start),
    endDate: formatIsoDate(end),
  };
}

export async function getForecast(
  locationQuery: string,
  requestedDays: number
): Promise<string | null> {
  const resolved = await resolveLocation(locationQuery);
  if (!resolved) {
    return null;
  }

  const safeDays = Math.max(1, Math.min(requestedDays, MAX_FORECAST_DAYS));
  const { startDate, endDate } = buildForecastRange(safeDays);
  const url = new URL(FORECAST_ENDPOINT);
  url.searchParams.set("latitude", String(resolved.latitude));
  url.searchParams.set("longitude", String(resolved.longitude));
  url.searchParams.set(
    "daily",
    [
      "weather_code",
      "temperature_2m_max",
      "temperature_2m_min",
      "precipitation_probability_max",
    ].join(",")
  );
  url.searchParams.set("timezone", "auto");
  url.searchParams.set("start_date", startDate);
  url.searchParams.set("end_date", endDate);

  const forecast = await fetchJson<ForecastResponse>(url);
  if (!forecast.daily) {
    return null;
  }

  const days: ForecastDay[] = forecast.daily.time.map((date, index) => ({
    date,
    condition: weatherCodeToDescription(forecast.daily!.weather_code[index]),
    maxTemperature: forecast.daily!.temperature_2m_max[index],
    minTemperature: forecast.daily!.temperature_2m_min[index],
    precipitationProbability:
      forecast.daily!.precipitation_probability_max?.[index] ?? null,
  }));

  const lines = days.map((day) => {
    const precipitation =
      day.precipitationProbability === null
        ? ""
        : `, precipitation chance ${day.precipitationProbability}%`;
    return `- ${day.date}: ${day.condition}, ${day.minTemperature}°C to ${day.maxTemperature}°C${precipitation}`;
  });

  const capNote =
    requestedDays > MAX_FORECAST_DAYS
      ? `\nRequested ${requestedDays} days; limited to ${MAX_FORECAST_DAYS} days by Open-Meteo.`
      : "";

  return `${safeDays}-day forecast for ${resolved.locationName}:${capNote}\n${lines.join("\n")}`;
}
