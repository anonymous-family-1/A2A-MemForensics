import { randomUUID } from "crypto";

export type BookingRequest = {
  guestName: string | null;
  email: string | null;
  creditCard: string | null;
  hotelName: string | null;
  city: string | null;
  checkInDate: string | null;
  checkOutDate: string | null;
  guests: number | null;
  roomType: string | null;
  specialRequests: string | null;
};

export type BookingConfirmation = {
  confirmationCode: string;
  hotelName: string;
  city: string | null;
  guestName: string;
  email: string;
  checkInDate: string;
  checkOutDate: string;
  guests: number;
  roomType: string;
  specialRequests: string | null;
  maskedCard: string;
};

function maskCard(creditCard: string): string {
  const digits = creditCard.replace(/\D/g, "");
  return `**** **** **** ${digits.slice(-4)}`;
}

function assertRequiredField(value: string | null, fieldName: string): string {
  if (!value || !value.trim()) {
    throw new Error(`Missing required field: ${fieldName}`);
  }

  return value.trim();
}

function normalizeGuests(guests: number | null): number {
  if (!guests || guests < 1) {
    return 1;
  }

  return Math.floor(guests);
}

function validateCreditCard(creditCard: string): string {
  const digits = creditCard.replace(/\D/g, "");
  if (digits.length < 13 || digits.length > 19) {
    throw new Error("Credit card number must contain 13 to 19 digits");
  }

  return digits;
}

function validateDate(value: string, fieldName: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error(`${fieldName} must be in YYYY-MM-DD format`);
  }

  return value;
}

export function createBookingConfirmation(request: BookingRequest): BookingConfirmation {
  const guestName = assertRequiredField(request.guestName, "guest_name");
  const email = assertRequiredField(request.email, "email");
  const hotelName = assertRequiredField(request.hotelName, "hotel_name");
  const checkInDate = validateDate(
    assertRequiredField(request.checkInDate, "check_in_date"),
    "check_in_date"
  );
  const checkOutDate = validateDate(
    assertRequiredField(request.checkOutDate, "check_out_date"),
    "check_out_date"
  );
  const creditCard = validateCreditCard(
    assertRequiredField(request.creditCard, "credit_card")
  );
  if (new Date(checkOutDate).getTime() <= new Date(checkInDate).getTime()) {
    throw new Error("check_out_date must be after check_in_date");
  }

  return {
    confirmationCode: `HTL-${randomUUID().slice(0, 8).toUpperCase()}`,
    hotelName,
    city: request.city,
    guestName,
    email,
    checkInDate,
    checkOutDate,
    guests: normalizeGuests(request.guests),
    roomType: request.roomType?.trim() || "standard room",
    specialRequests: request.specialRequests?.trim() || null,
    maskedCard: maskCard(creditCard),
  };
}
