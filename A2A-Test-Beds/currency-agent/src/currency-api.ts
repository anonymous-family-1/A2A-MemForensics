type RateResponse = {
  amount?: number;
  base?: string;
  quote?: string;
  rate?: number;
};

const RATE_ENDPOINT = "https://api.frankfurter.dev/v2/rate";

export async function getUsdConversionRate(targetCurrency: string): Promise<number | null> {
  const url = new URL(`${RATE_ENDPOINT}/USD/${targetCurrency.toUpperCase()}`);
  const response = await fetch(url);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Frankfurter request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as RateResponse;
  return payload.rate ?? null;
}
