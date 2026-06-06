type GeocodingResponse = {
  results?: Array<{
    name: string;
    country?: string;
    admin1?: string;
    timezone: string;
  }>;
};

type TimeData = {
  locationName: string;
  timezone: string;
  localTime: string;
};

const GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search";

function formatLocationName(result: NonNullable<GeocodingResponse["results"]>[number]): string {
  return [result.name, result.admin1, result.country].filter(Boolean).join(", ");
}

async function fetchJson<T>(url: URL): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Open-Meteo geocoding request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function formatLocalTime(timezone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(new Date());
}

export async function getLocalTime(locationQuery: string): Promise<TimeData | null> {
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
    locationName: formatLocationName(match),
    timezone: match.timezone,
    localTime: formatLocalTime(match.timezone),
  };
}
