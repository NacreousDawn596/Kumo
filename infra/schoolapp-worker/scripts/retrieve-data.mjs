// Retrieve a student's SchoolApp data for verification purposes.
//
// Usage (credentials come from the environment, never hardcoded):
//   SCHOOLAPP_EMAIL=you@example.com SCHOOLAPP_PASSWORD=... node retrieve-data.mjs
//
// Prints the parsed profile (identity + stable "Code"), grades, and absences.
// The password is never printed or logged.

import { SchoolAppClient } from "schoolapp";

const email = process.env.SCHOOLAPP_EMAIL;
const password = process.env.SCHOOLAPP_PASSWORD;

if (!email || !password) {
  console.error("Set SCHOOLAPP_EMAIL and SCHOOLAPP_PASSWORD.");
  process.exit(1);
}

const client = new SchoolAppClient();
const ok = await client.login(email, password);
if (!ok) {
  console.error("Login failed.");
  process.exit(1);
}

console.log("=== PROFILE ===");
const profile = await client.getProfile();
console.log(JSON.stringify(profile, null, 2));

// Stable subject identifier used by Kumo.
const personal = profile?.personal_info || {};
const admin = profile?.administrative_info || {};
const code = personal.Code || personal["CNE/Masar"] || admin.Code;
console.log("\n=== STABLE SUBJECT (Code) ===");
console.log(code || "(not found)");

console.log("\n=== GRADES (element notes) ===");
try {
  const grades = await client.getCurrentElemNote();
  console.log(JSON.stringify(grades, null, 2));
} catch (e) {
  console.error("grades error:", e.message);
}

console.log("\n=== ABSENCES ===");
try {
  const absences = await client.getAbsences();
  console.log(JSON.stringify(absences, null, 2));
} catch (e) {
  console.error("absences error:", e.message);
}
