import RESEARCH from '../data/research_data.json';

function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function seeded(h, n) { return ((h >>> n) & 0xff) / 255; }

const BREEDS = [
  'Holstein-Friesian',
  'HF × Bunaji (White Fulani)',
  'HF × Sokoto Gudali',
  'Brown Swiss × Bunaji',
  'Azawak × Holstein-Friesian',
];

const SIRES = ['Danone Maximus', 'Sunridge Apollo', 'Kano Chief 44', 'Lagos Star Elite', 'Abuja Baron'];
const DAMS  = ['Milkmaid 12', 'Rose of Zaria', 'Fatima 7', 'Keffi Queen', 'Plateau Pride'];
const VETS  = ['Dr. Abubakar Musa', 'Dr. Ngozi Okonkwo', 'Dr. Ibrahim Yusuf'];

const VACCINES = [
  'FMD (Foot-and-Mouth) Bivalent',
  'Brucellosis S19 Vaccine',
  'CBPP (Contagious Bovine Pleuropneumonia)',
  'Blackleg (Clostridium chauvoei)',
  'Anthrax Spore Vaccine',
  'Lumpy Skin Disease Vaccine',
];

const TREATMENTS = [
  'Oxytetracycline LA — respiratory infection',
  'Albendazole oral drench — GI parasites',
  'Amitraz dip — tick burden management',
  'Calcium borogluconate IV — hypocalcaemia',
  'Vitamin B12 + Selenium injection',
  'Flunixin meglumine — post-calving pain',
];

const LFT_RESULTS = ['Visible', 'Faint, but visible', 'Visible', 'Visible', 'Not visible', 'Faint, but visible'];

function addDays(dateStr, n) {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function woodLactation(dim, peak, a = 0.05) {
  // Wood's model: y = A * dim^b * e^(-c*dim), simplified to a peak-scaled Gamma curve
  const b = 0.18, c = 0.0045;
  const raw = Math.pow(dim, b) * Math.exp(-c * dim);
  const peakRaw = Math.pow(1 / (b / c), b) * Math.exp(-b);
  return peak * (raw / peakRaw);
}

export function getCowMockData(cowId) {
  const h = hash(cowId);

  const breed = BREEDS[h % BREEDS.length];
  const birthYear = 2019 + (h % 4);
  const birthMonth = 1 + ((h >> 3) % 12);
  const birthDay = 1 + ((h >> 6) % 27);
  const dob = `${birthYear}-${String(birthMonth).padStart(2, '0')}-${String(birthDay).padStart(2, '0')}`;
  const ageYears = 2026 - birthYear;

  const nCalvings = 1 + (h % 3);
  const lastCalvingDim = 30 + ((h >> 8) % 200); // days in milk at data start
  const peakYield = 12 + seeded(h, 4) * 14; // 12–26 litres/day

  // Calving history (dates before data window Apr 2025)
  const calvings = [];
  let calvDate = `2025-04-08`;
  calvDate = addDays(calvDate, -(lastCalvingDim));
  for (let i = 0; i < nCalvings; i++) {
    calvDate = addDays(calvDate, -(280 + ((h >> (i * 3)) % 100)));
    calvings.unshift({
      lactation: nCalvings - i,
      date: calvDate,
      calving: i === 0 ? 'Normal' : ['Normal', 'Assisted', 'Normal', 'Normal'][i % 4],
      calf_sex: (h >> (i + 5)) % 2 === 0 ? 'Heifer' : 'Bull',
      peak_yield: `${(peakYield * (0.85 + seeded(h, i + 9) * 0.3)).toFixed(1)} L/day`,
    });
  }

  // Milk yield — 90 days ending Sep 12, 2025
  const milkYield = [];
  for (let d = 0; d < 90; d++) {
    const date = addDays('2025-06-14', d);
    const dim = lastCalvingDim + d;
    const base = woodLactation(dim, peakYield);
    const noise = (seeded(hash(cowId + d), 2) - 0.5) * 2.5;
    milkYield.push({ date, yield: Math.max(0, base + noise).toFixed(1) });
  }

  // Health records — 4–6 events
  const nHealth = 4 + (h % 3);
  const healthRecords = [];
  for (let i = 0; i < nHealth; i++) {
    const daysAgo = 30 + ((hash(cowId + 'h' + i) % 300));
    const date = addDays('2025-09-12', -daysAgo);
    const isVax = (h >> (i + 1)) % 3 !== 0;
    healthRecords.push({
      date,
      type: isVax ? 'Vaccination' : 'Treatment',
      description: isVax ? VACCINES[(h + i) % VACCINES.length] : TREATMENTS[(h + i) % TREATMENTS.length],
      vet: VETS[(h + i) % VETS.length],
    });
  }
  healthRecords.sort((a, b) => b.date.localeCompare(a.date));

  // P4 LFT test history — 3–5 tests
  const nP4 = 3 + (h % 3);
  const p4Tests = [];
  for (let i = 0; i < nP4; i++) {
    const daysAgo = 10 + i * 21 + ((hash(cowId + 'p' + i) % 10));
    const date = addDays('2025-09-12', -daysAgo);
    const result = LFT_RESULTS[(h + i) % LFT_RESULTS.length];
    p4Tests.push({ date, result, notes: result === 'Not visible' ? 'Low P4 — not in luteal phase' : result === 'Faint, but visible' ? 'Mid P4 — early luteal' : 'High P4 — luteal phase confirmed' });
  }
  p4Tests.sort((a, b) => b.date.localeCompare(a.date));

  const summary = RESEARCH.cow_summary.find(c => c.cow_id === cowId) || {};

  return {
    cow_id: cowId,
    tag: summary.tag || cowId,
    breed,
    dob,
    age_years: ageYears,
    sire: SIRES[h % SIRES.length],
    dam: DAMS[h % DAMS.length],
    status: lastCalvingDim < 305 ? 'Lactating' : 'Dry',
    lactation_number: nCalvings,
    dim: lastCalvingDim,
    calvings,
    milk_yield: milkYield,
    health_records: healthRecords,
    p4_tests: p4Tests,
    summary,
    ts: RESEARCH.cow_ts[cowId] || [],
  };
}

export { RESEARCH };
