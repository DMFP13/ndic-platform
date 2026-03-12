import { apiClient } from './client.js';

// ---------------------------------------------------------------------------
// Mock fallback helper
// If the API call fails (any error, including 404), returns the mock data
// wrapped in a resolved promise that mimics an axios response shape.
// ---------------------------------------------------------------------------
async function _mockFallback(apiFn, mockData) {
  try {
    return await apiFn();
  } catch {
    return { data: mockData, _isMock: true };
  }
}

// ---------------------------------------------------------------------------
// Government endpoints
// ---------------------------------------------------------------------------

export function getDiseaseSurveillance(timelineFilter = '30d') {
  const MOCK = [
    { id: 1, lat: 9.05, lng: 7.49, disease: 'ECF', status: 'confirmed', location: 'FCT', animals_affected: 45, date: '2024-03-10' },
    { id: 2, lat: 12.0, lng: 8.5, disease: 'FMD', status: 'suspected', location: 'Kano', animals_affected: 120, date: '2024-03-08' },
    { id: 3, lat: 7.38, lng: 3.93, disease: 'Mastitis', status: 'resolved', location: 'Ogun', animals_affected: 12, date: '2024-03-01' },
    { id: 4, lat: 11.08, lng: 7.72, disease: 'Trypanosomiasis', status: 'suspected', location: 'Kaduna', animals_affected: 78, date: '2024-03-09' },
    { id: 5, lat: 13.15, lng: 5.23, disease: 'Brucellosis', status: 'confirmed', location: 'Sokoto', animals_affected: 34, date: '2024-03-07' },
    { id: 6, lat: 9.92, lng: 8.89, disease: 'LSD', status: 'suspected', location: 'Plateau', animals_affected: 56, date: '2024-03-11' },
  ];
  return _mockFallback(
    () => apiClient.get('/government/disease-map', { params: { timeline: timelineFilter } }),
    MOCK
  );
}

export function getProductionTrends() {
  const MOCK = [
    { state: 'Kano', liters: 45200, trend: 5 },
    { state: 'Kaduna', liters: 38900, trend: -3 },
    { state: 'Sokoto', liters: 29100, trend: 2 },
    { state: 'Ogun', liters: 18700, trend: 8 },
    { state: 'Enugu', liters: 12400, trend: -10 },
    { state: 'FCT', liters: 9800, trend: 1 },
  ];
  return _mockFallback(
    () => apiClient.get('/government/production-trends'),
    MOCK
  );
}

export function getClimateRiskMap() {
  const MOCK = [
    { region: 'North', bounds: [[10, 4], [14, 15]], droughtRisk: 'high', floodRisk: 'low' },
    { region: 'South-West', bounds: [[4, 2], [8, 6]], droughtRisk: 'low', floodRisk: 'high' },
    { region: 'South-East', bounds: [[4, 6], [8, 10]], droughtRisk: 'low', floodRisk: 'medium' },
    { region: 'Middle Belt', bounds: [[7, 3], [10, 12]], droughtRisk: 'medium', floodRisk: 'medium' },
  ];
  return _mockFallback(
    () => apiClient.get('/government/climate-risk-map'),
    MOCK
  );
}

export function getEarlyWarnings() {
  const MOCK = [
    { id: 1, severity: 'critical', title: 'FMD Outbreak Escalating', location: 'Kano LGA', description: 'Confirmed FMD cases increased 40% in 72 hours. 120 animals affected across 3 farms.', action: 'Activate emergency quarantine zones. Dispatch veterinary response team.', status: 'active', date: '2024-03-10' },
    { id: 2, severity: 'critical', title: 'Brucellosis Spread Risk', location: 'Sokoto', description: 'Brucellosis confirmed in breeding herd. High cross-contamination risk at shared watering points.', action: 'Mandatory testing for all farms within 50km radius.', status: 'active', date: '2024-03-07' },
    { id: 3, severity: 'warning', title: 'ECF Monitoring Required', location: 'FCT', description: 'ECF cases detected in 2 farms. Tick population above seasonal threshold.', action: 'Increase tick surveillance. Recommend prophylactic treatment.', status: 'monitoring', date: '2024-03-09' },
    { id: 4, severity: 'warning', title: 'Drought Stress — Feed Shortage Risk', location: 'Katsina', description: 'Pasture quality index dropped 22% vs 30-day average. Feed price inflation risk.', action: 'Alert registered farms. Subsidized feed procurement advisory.', status: 'monitoring', date: '2024-03-08' },
    { id: 5, severity: 'info', title: 'Mastitis Cluster Resolved', location: 'Ogun', description: 'Treatment programme completed. All 12 affected animals returned to healthy status.', action: 'Continue monthly monitoring. Document treatment outcomes.', status: 'resolved', date: '2024-03-05' },
  ];
  return _mockFallback(
    () => apiClient.get('/government/early-warnings'),
    MOCK
  );
}

export function getPolicyAnalytics() {
  const MOCK = {
    herd_growth_yoy: 4.2,
    productivity_l_per_head: 8.7,
    mortality_rate: 2.1,
    zebu_percent: 68,
    herd_growth_trend: 1.1,
    productivity_trend: 0.3,
    mortality_trend: -0.2,
    zebu_trend: -0.5,
    total_animals: 284600,
    healthy_pct: 91.4,
    at_risk_pct: 6.2,
    treated_pct: 2.4,
    total_trend: 2.1,
    healthy_trend: -0.3,
    at_risk_trend: 0.8,
    treated_trend: -0.5,
  };
  return _mockFallback(
    () => apiClient.get('/government/policy-analytics'),
    MOCK
  );
}

// ---------------------------------------------------------------------------
// Processor endpoints
// ---------------------------------------------------------------------------

export function getSupplyForecast(processorId) {
  const MOCK = {
    forecast: Array.from({ length: 30 }, (_, i) => ({
      day: i + 1,
      forecast: Math.round(5000 + Math.sin(i / 5) * 300 + i * 20),
      lower: Math.round(4500 + Math.sin(i / 5) * 300 + i * 15),
      upper: Math.round(5500 + Math.sin(i / 5) * 300 + i * 25),
      historical: i < 14 ? Math.round(4800 + Math.sin(i / 4) * 250 + i * 18) : null,
    })),
    suppliers: [
      { id: 's1', name: 'Kano Cooperative A', location: 'Kano', daily_avg: 1240, quality_grade: { A: 60, B: 30, C: 10 }, health_status: 'healthy', trend: 3 },
      { id: 's2', name: 'Plateau Dairy Hub', location: 'Plateau', daily_avg: 980, quality_grade: { A: 45, B: 40, C: 15 }, health_status: 'at_risk', trend: -8 },
      { id: 's3', name: 'Kaduna Farms Ltd', location: 'Kaduna', daily_avg: 1560, quality_grade: { A: 70, B: 25, C: 5 }, health_status: 'healthy', trend: 5 },
      { id: 's4', name: 'FCT Small Holders', location: 'FCT', daily_avg: 420, quality_grade: { A: 35, B: 45, C: 20 }, health_status: 'at_risk', trend: -12 },
    ],
  };
  return _mockFallback(
    () => apiClient.get(`/processors/${processorId}/supply-dashboard`),
    MOCK
  );
}

export function getBenchmarking(processorId) {
  const MOCK = {
    your_metrics: { daily_volume: 4200, avg_quality_grade: 'B+', price_paid: 285 },
    peer_median: { daily_volume: 3800, avg_quality_grade: 'B', price_paid: 295 },
    best_in_class: { daily_volume: 7200, avg_quality_grade: 'A', price_paid: 310 },
    interpretation: 'Your daily volume is 10.5% above peer median, indicating strong supplier relationships. Quality grade is marginally above median. Price paid is 3.4% below median — review pricing strategy to retain top-grade suppliers.',
  };
  return _mockFallback(
    () => apiClient.get(`/processors/${processorId}/benchmarking`),
    MOCK
  );
}

export function getCostAnalysis(processorId) {
  const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];
  const MOCK = {
    price_trend: months.map((m, i) => ({
      month: m,
      your_price: Math.round(270 + Math.sin(i / 2) * 20 + i * 2.5),
      import_parity: Math.round(320 + Math.sin(i / 3) * 15 + i * 1.8),
    })),
    risks: [
      { level: 'critical', name: 'Supply Concentration Risk', description: 'Two suppliers account for 67% of total intake. Disruption would immediately impact operations.', affected_suppliers: ['Kaduna Farms Ltd', 'Kano Cooperative A'] },
      { level: 'warning', name: 'Quality Grade Degradation', description: 'Grade A percentage declining 2% per month from FCT Small Holders. Blended quality at risk.', affected_suppliers: ['FCT Small Holders'] },
      { level: 'info', name: 'Seasonal Volume Dip Forecast', description: 'Historical data shows 15-20% volume reduction in Jul-Aug. Recommend advance contracting.', affected_suppliers: ['All suppliers'] },
    ],
  };
  return _mockFallback(
    () => apiClient.get(`/processors/${processorId}/cost-analysis`),
    MOCK
  );
}

// ---------------------------------------------------------------------------
// Farm endpoints
// ---------------------------------------------------------------------------

export function getFarmDashboard(farmId) {
  const MOCK = {
    summary: {
      total_animals: 48,
      healthy: 41,
      at_risk: 5,
      critical: 2,
      daily_milk_yield: 387.6,
      yield_trend: 3.2,
      health_trend: -1.1,
    },
    animals: [
      { id: 'a1', tag: 'NG-001', breed: 'Bunaji', status: 'healthy', health_score: 82, yield: 12.4, estrus_prob: 0.82, fever_prob: 0.05, mastitis_risk: 0.12, temp_history: [38.4, 38.3, 38.5, 38.4, 38.2, 38.4, 38.3], yield_history: [12.1, 12.4, 12.2, 12.6, 12.3, 12.4, 12.4], treatment_log: [{ date: '2024-02-15', action: 'Deworming', vet: 'Dr. Musa' }, { date: '2024-01-20', action: 'FMD Vaccination', vet: 'Dr. Musa' }], recommendation: 'Animal is in peak estrus window. Recommend AI within 12-18 hours for optimal conception rate.' },
      { id: 'a2', tag: 'NG-002', breed: 'Friesian', status: 'at_risk', health_score: 48, yield: 6.2, estrus_prob: 0.05, fever_prob: 0.78, mastitis_risk: 0.65, temp_history: [38.5, 38.9, 39.2, 39.6, 39.8, 40.1, 40.3], yield_history: [11.2, 10.8, 9.4, 8.1, 7.6, 6.8, 6.2], treatment_log: [{ date: '2024-03-09', action: 'Antibiotic administered (Oxytetracycline)', vet: 'Dr. Adaeze' }, { date: '2024-03-08', action: 'Blood sample taken — pending results', vet: 'Dr. Adaeze' }, { date: '2024-02-28', action: 'Mastitis screening — negative', vet: 'Dr. Musa' }], recommendation: 'High fever risk detected. Isolate immediately. Begin broad-spectrum antibiotic treatment pending culture results. Monitor every 4 hours.' },
      { id: 'a3', tag: 'NG-003', breed: 'Bunaji', status: 'healthy', health_score: 77, yield: 9.8, estrus_prob: 0.12, fever_prob: 0.08, mastitis_risk: 0.18, temp_history: [38.3, 38.4, 38.2, 38.5, 38.3, 38.4, 38.3], yield_history: [9.6, 9.7, 9.9, 9.8, 9.8, 9.9, 9.8], treatment_log: [{ date: '2024-02-10', action: 'Routine health check — passed', vet: 'Dr. Musa' }], recommendation: 'Healthy. Schedule routine hoof trimming in next 2 weeks.' },
      { id: 'a4', tag: 'NG-004', breed: 'Friesian x Bunaji', status: 'critical', health_score: 22, yield: 2.1, estrus_prob: 0.02, fever_prob: 0.91, mastitis_risk: 0.88, temp_history: [38.6, 39.1, 39.8, 40.2, 40.5, 40.9, 41.1], yield_history: [10.2, 8.5, 6.1, 4.8, 3.9, 2.8, 2.1], treatment_log: [{ date: '2024-03-10', action: 'IV fluids + Flunixin started', vet: 'Dr. Adaeze' }, { date: '2024-03-10', action: 'Mastitis confirmed LH quarter', vet: 'Dr. Adaeze' }, { date: '2024-03-09', action: 'Emergency vet called', vet: 'Dr. Adaeze' }], recommendation: 'CRITICAL: Confirmed mastitis + hyperthermia. Intensive care protocol active. Do not milk affected quarter. Re-evaluate in 24 hours.' },
      { id: 'a5', tag: 'NG-005', breed: 'Bunaji', status: 'healthy', health_score: 91, yield: 14.2, estrus_prob: 0.15, fever_prob: 0.03, mastitis_risk: 0.06, temp_history: [38.2, 38.1, 38.3, 38.2, 38.3, 38.1, 38.2], yield_history: [14.0, 14.2, 14.1, 14.4, 14.2, 14.3, 14.2], treatment_log: [{ date: '2024-01-15', action: 'Annual vaccination completed', vet: 'Dr. Musa' }], recommendation: 'Top performer. Candidate for breed improvement programme. Consider embryo flush.' },
      { id: 'a6', tag: 'NG-006', breed: 'Friesian', status: 'at_risk', health_score: 55, yield: 7.9, estrus_prob: 0.35, fever_prob: 0.42, mastitis_risk: 0.38, temp_history: [38.4, 38.6, 38.8, 38.9, 39.0, 39.1, 39.2], yield_history: [9.8, 9.5, 9.1, 8.8, 8.5, 8.2, 7.9], treatment_log: [{ date: '2024-03-07', action: 'Subclinical mastitis screening — borderline', vet: 'Dr. Musa' }], recommendation: 'Elevated temperature trend. Monitor closely. Consider preventive antibiotic course if temperature exceeds 39.5°C within 24 hours.' },
      { id: 'a7', tag: 'NG-007', breed: 'Bunaji', status: 'healthy', health_score: 73, yield: 8.6, estrus_prob: 0.08, fever_prob: 0.11, mastitis_risk: 0.14, temp_history: [38.3, 38.4, 38.4, 38.5, 38.3, 38.4, 38.4], yield_history: [8.4, 8.5, 8.6, 8.7, 8.6, 8.6, 8.6], treatment_log: [], recommendation: 'Healthy. No action required. Next routine check in 14 days.' },
      { id: 'a8', tag: 'NG-008', breed: 'Friesian x Bunaji', status: 'at_risk', health_score: 61, yield: 8.1, estrus_prob: 0.22, fever_prob: 0.31, mastitis_risk: 0.44, temp_history: [38.5, 38.6, 38.7, 38.9, 38.8, 38.9, 39.0], yield_history: [9.2, 9.0, 8.8, 8.6, 8.4, 8.2, 8.1], treatment_log: [{ date: '2024-03-05', action: 'Mastitis risk flagged by AI system', vet: 'System' }], recommendation: 'Moderate mastitis risk. Perform California Mastitis Test (CMT). Begin teat dipping protocol immediately.' },
      { id: 'a9', tag: 'NG-009', breed: 'Bunaji', status: 'healthy', health_score: 85, yield: 11.3, estrus_prob: 0.71, fever_prob: 0.04, mastitis_risk: 0.08, temp_history: [38.2, 38.2, 38.3, 38.3, 38.2, 38.2, 38.3], yield_history: [11.1, 11.2, 11.3, 11.4, 11.3, 11.3, 11.3], treatment_log: [{ date: '2024-03-01', action: 'Estrus observed — marked for AI', vet: 'Dr. Musa' }], recommendation: 'Estrus probability elevated (71%). Optimal AI window is today. Schedule insemination.' },
      { id: 'a10', tag: 'NG-010', breed: 'Friesian', status: 'healthy', health_score: 79, yield: 13.1, estrus_prob: 0.09, fever_prob: 0.07, mastitis_risk: 0.10, temp_history: [38.3, 38.4, 38.3, 38.4, 38.5, 38.4, 38.3], yield_history: [13.0, 13.1, 13.2, 13.1, 13.0, 13.1, 13.1], treatment_log: [{ date: '2024-02-20', action: 'Hoof trimming completed', vet: 'Dr. Adaeze' }], recommendation: 'Good health status. Maintain current feeding regimen.' },
    ],
    financials: {
      cost_per_liter: 142,
      monthly_total_cost: 1680000,
      projected_revenue: 2322000,
      net_margin_pct: 27.6,
      sparkline: [22.1, 24.3, 25.8, 26.2, 27.0, 27.6],
    },
    interventions: {
      recommended: [
        { tag: 'NG-009', condition: 'Estrus detected', action: 'Artificial Insemination', due: '2024-03-11' },
        { tag: 'NG-001', condition: 'Peak estrus window', action: 'Artificial Insemination', due: '2024-03-11' },
        { tag: 'NG-008', condition: 'Mastitis risk moderate', action: 'California Mastitis Test + teat dipping', due: '2024-03-12' },
        { tag: 'NG-006', condition: 'Elevated temperature trend', action: 'Temperature monitoring every 6 hours', due: '2024-03-11' },
      ],
      in_progress: [
        { tag: 'NG-004', condition: 'Clinical mastitis + hyperthermia', action: 'IV fluids + Flunixin + isolation', due: '2024-03-12' },
        { tag: 'NG-002', condition: 'Suspected systemic infection', action: 'Oxytetracycline course (Day 2 of 5)', due: '2024-03-14' },
      ],
      completed: [
        { tag: 'NG-003', condition: 'Routine hoof check', action: 'Hoof inspection — passed', due: '2024-03-09' },
        { tag: 'NG-010', condition: 'Hoof trimming', action: 'Completed by Dr. Adaeze', due: '2024-03-08' },
        { tag: 'NG-007', condition: 'Routine health check', action: 'All vitals normal', due: '2024-03-07' },
      ],
    },
    climate: {
      risk_level: 'medium',
      drought_forecast: Array.from({ length: 30 }, (_, i) => ({
        day: i + 1,
        risk: Math.max(0, Math.min(100, 35 + Math.sin(i / 4) * 20 + i * 0.8)),
      })),
      recommendation: 'Moderate drought risk over next 30 days. Begin supplemental feed procurement. Review borehole water reserve levels. Consider early dry-season grazing rotation.',
    },
  };
  return _mockFallback(
    () => apiClient.get(`/farms/${farmId}/dashboard`),
    MOCK
  );
}

export function getAnimalProfile(farmId, animalId) {
  return _mockFallback(
    () => apiClient.get(`/farms/${farmId}/animals/${animalId}`),
    null
  );
}

export function getFarmForecast(farmId, daysAhead = 30) {
  const MOCK = Array.from({ length: daysAhead }, (_, i) => ({
    day: i + 1,
    yield: Math.round((387.6 + Math.sin(i / 6) * 20 + i * 0.3) * 10) / 10,
  }));
  return _mockFallback(
    () => apiClient.get(`/farms/${farmId}/forecast`, { params: { days_ahead: daysAhead } }),
    MOCK
  );
}

// ---------------------------------------------------------------------------
// Lender endpoints
// ---------------------------------------------------------------------------

export function getLenderPortfolio(lenderId) {
  const MOCK = {
    total_loans: 14,
    total_collateral_ngn: 48700000,
    at_risk_loans: 3,
    overall_risk: 'medium',
    loans: [
      { id: 'L001', farm: 'Kano Farm Co.', location: 'Kano', loan_amount: 2500000, collateral_value: 3800000, health_score: 78, risk: 'low', trend: 'up', loan_type: 'Working Capital', maturity: '2025-06', animals: { lactating: 28, breeding: 12, calves: 6, bulls: 2 }, valuation_confidence: 92, health_alerts: [] },
      { id: 'L002', farm: 'Kaduna Dairy', location: 'Kaduna', loan_amount: 1800000, collateral_value: 2100000, health_score: 52, risk: 'medium', trend: 'down', loan_type: 'Asset Finance', maturity: '2024-09', animals: { lactating: 15, breeding: 8, calves: 4, bulls: 1 }, valuation_confidence: 71, health_alerts: ['3 animals flagged with fever symptoms', 'Milk yield declining 8% month-on-month'] },
      { id: 'L003', farm: 'Sokoto Agri Hub', location: 'Sokoto', loan_amount: 3200000, collateral_value: 4500000, health_score: 84, risk: 'low', trend: 'up', loan_type: 'Expansion Loan', maturity: '2026-03', animals: { lactating: 42, breeding: 18, calves: 11, bulls: 4 }, valuation_confidence: 88, health_alerts: [] },
      { id: 'L004', farm: 'Ogun Dairy Ltd', location: 'Ogun', loan_amount: 950000, collateral_value: 880000, health_score: 31, risk: 'high', trend: 'down', loan_type: 'Working Capital', maturity: '2024-06', animals: { lactating: 8, breeding: 4, calves: 2, bulls: 1 }, valuation_confidence: 45, health_alerts: ['Collateral value below loan principal', 'Disease outbreak confirmed — 3 animals in isolation', 'Production down 42% from baseline'] },
      { id: 'L005', farm: 'FCT Cooperative', location: 'FCT', loan_amount: 1200000, collateral_value: 1650000, health_score: 67, risk: 'medium', trend: 'stable', loan_type: 'Working Capital', maturity: '2025-01', animals: { lactating: 18, breeding: 7, calves: 5, bulls: 2 }, valuation_confidence: 79, health_alerts: ['Subclinical mastitis risk in 2 animals'] },
    ],
    pipeline: [
      { farm: 'Plateau Dairy Hub', location: 'Plateau', current_loan: 800000, recommended_modification: 'Refinance at lower rate — herd health improved significantly', health_score: 81, opportunity: 'refinance' },
      { farm: 'Borno Agro', location: 'Borno', current_loan: 0, recommended_modification: 'New loan opportunity — 45-head herd, healthy baseline', health_score: 76, opportunity: 'new_loan' },
    ],
    early_warnings: [
      { category: 'Health Decline', severity: 'critical', farm: 'Ogun Dairy Ltd', detail: 'Disease outbreak + 42% production decline. Collateral value at risk. Recommend immediate site visit.', date: '2024-03-10' },
      { category: 'Health Decline', severity: 'warning', farm: 'Kaduna Dairy', detail: 'Fever symptoms in 3 animals. Yield declining. Monitor closely over next 14 days.', date: '2024-03-09' },
      { category: 'Climate Risk', severity: 'warning', farm: 'Sokoto Agri Hub', detail: 'Drought forecast for next 30 days may impact pasture quality and feed costs.', date: '2024-03-08' },
      { category: 'Maturity Risk', severity: 'info', farm: 'FCT Cooperative', detail: 'Loan matures in 90 days. Recommend early renewal discussion given stable performance.', date: '2024-03-07' },
      { category: 'Maturity Risk', severity: 'critical', farm: 'Ogun Dairy Ltd', detail: 'Loan matures in 87 days. Farm performance deteriorating. High default risk.', date: '2024-03-10' },
    ],
  };
  return _mockFallback(
    () => apiClient.get(`/lenders/${lenderId}/portfolio-summary`),
    MOCK
  );
}

export function getLenderLoans(lenderId, status = 'all') {
  return _mockFallback(
    () => apiClient.get(`/lenders/${lenderId}/loans`, { params: { status } }),
    []
  );
}

export function getCollateralAssessment(lenderId, farmId) {
  return _mockFallback(
    () => apiClient.get(`/lenders/${lenderId}/farm/${farmId}/collateral-assessment`),
    null
  );
}

// ---------------------------------------------------------------------------
// Cow Passport endpoints
// ---------------------------------------------------------------------------

function _mockPassport(farmId, animalId) {
  const seed = animalId.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const rng = (n) => ((seed * 1103515245 + 12345) & 0x7fffffff) % n;
  const breeds = ['Bunaji (White Fulani)', 'Friesian', 'Friesian × Bunaji', 'Rahaji', 'Sokoto Gudali'];
  const colours = ['White', 'Black and white', 'Fawn', 'Brown', 'Brown and white'];
  const dob = new Date(Date.now() - (365 * 3 + rng(365 * 5)) * 86400000);
  const ageMonths = Math.floor((Date.now() - dob.getTime()) / (30.44 * 86400000));

  const mockVetRecords = [
    {
      id: `vr-vac1-${animalId}`, record_type: 'vaccination',
      record_date: new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10),
      title: 'FMD Vaccination', description: 'Annual foot-and-mouth disease vaccination',
      vaccine_name: 'FOTIVAX®', vaccine_batch: `FV${2000 + rng(8000)}`,
      next_due_date: new Date(Date.now() + 275 * 86400000).toISOString().slice(0, 10),
      vet_name: 'Dr. Musa Ibrahim', vet_contact: 'musa.ibrahim@ndic.ng', is_mock: true,
    },
    {
      id: `vr-vac2-${animalId}`, record_type: 'vaccination',
      record_date: new Date(Date.now() - 45 * 86400000).toISOString().slice(0, 10),
      title: 'Brucellosis Vaccination', description: 'S19 Brucella abortus — herd campaign',
      vaccine_name: 'Strain 19', vaccine_batch: `B${100 + rng(900)}`,
      next_due_date: null,
      vet_name: 'Dr. Adaeze Okonkwo', vet_contact: 'adaeze.okonkwo@ndic.ng',
      notes: 'Single dose, permanent immunity confirmed.', is_mock: true,
    },
    {
      id: `vr-tx1-${animalId}`, record_type: 'treatment',
      record_date: new Date(Date.now() - 18 * 86400000).toISOString().slice(0, 10),
      title: 'Oxytetracycline — respiratory infection',
      description: 'Suspected respiratory infection following herd movement.',
      drug_name: 'Oxytetracycline LA 200', dosage: '20 mg/kg', route: 'IM',
      duration_days: 3, withdrawal_period_days: 28,
      vet_name: 'Dr. Musa Ibrahim', notes: 'Monitor temperature daily for 5 days.', is_mock: true,
    },
    {
      id: `vr-wt1-${animalId}`, record_type: 'weight_check',
      record_date: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
      title: 'Routine Weight Check',
      description: `Weight recorded: ${340 + rng(110)} kg`,
      vet_name: 'Farm Manager', is_mock: true,
    },
    {
      id: `vr-note1-${animalId}`, record_type: 'note',
      record_date: new Date(Date.now() - 5 * 86400000).toISOString().slice(0, 10),
      title: 'Behavioural observation',
      description: 'Animal appeared slightly lethargic at morning check. Appetite normal. No temperature elevation.',
      vet_name: 'Farm Manager', is_mock: true,
    },
  ];

  // Generate 30-day time-series
  const now = Date.now();
  const series = Array.from({ length: 60 }, (_, i) => {
    const ts = new Date(now - (60 - i) * 12 * 3600000);
    const noise = () => (Math.random() - 0.5) * 2;
    return {
      timestamp: ts.toISOString(),
      temperature_celsius: +(38.3 + noise() * 0.15 + Math.sin(i / 6) * 0.2).toFixed(2),
      weight_kg: +(380 + noise() * 0.8 + i * 0.05).toFixed(1),
      milk_yield_liters: +(11 + noise() * 0.4 + Math.sin(i / 8) * 0.6).toFixed(2),
      heart_rate_bpm: Math.round(65 + noise() * 2),
      activity_index: +Math.max(0, Math.min(100, 55 + noise() * 8 + Math.sin(i / 4) * 12)).toFixed(1),
      feed_intake_kg: +(15 + noise() * 0.5).toFixed(2),
      is_mock: true,
    };
  });

  const latest = series[series.length - 1];

  return {
    is_mock: true,
    animal_id: animalId,
    farm_id: farmId,
    identity: {
      tag: `NG-${100 + rng(900)}`,
      microchip: `MC${10000000 + rng(89999999)}`,
      breed: breeds[rng(breeds.length)],
      sex: rng(4) === 0 ? 'Male' : 'Female',
      date_of_birth: dob.toISOString().slice(0, 10),
      age_months: ageMonths,
      colour_markings: colours[rng(colours.length)],
      dam_tag: `NG-0${50 + rng(50)}`,
      sire_tag: `NG-00${1 + rng(49)}`,
      acquired_date: new Date(dob.getTime() + rng(90) * 86400000).toISOString().slice(0, 10),
      status: ['healthy', 'healthy', 'healthy', 'at_risk', 'critical'][rng(5)],
    },
    current_sensors: { ...latest, as_of: latest.timestamp },
    sensor_series: series,
    vet_records: mockVetRecords,
    photos: [],
  };
}

export function getAnimalPassport(farmId, animalId) {
  return _mockFallback(
    () => apiClient.get(`/farms/${farmId}/animals/${animalId}/passport`),
    _mockPassport(farmId, animalId)
  );
}

export function getSensorHistory(farmId, animalId, days = 30) {
  return _mockFallback(
    () => apiClient.get(`/farms/${farmId}/animals/${animalId}/sensor-history`, { params: { days } }),
    { animal_id: animalId, is_mock: true, readings: _mockPassport(farmId, animalId).sensor_series }
  );
}

export function createVetRecord(farmId, animalId, data) {
  return apiClient.post(`/farms/${farmId}/animals/${animalId}/vet-records`, data);
}

export function updateVetRecord(farmId, animalId, recordId, data) {
  return apiClient.put(`/farms/${farmId}/animals/${animalId}/vet-records/${recordId}`, data);
}

export function deleteVetRecord(farmId, animalId, recordId) {
  return apiClient.delete(`/farms/${farmId}/animals/${animalId}/vet-records/${recordId}`);
}

export function uploadAnimalPhoto(farmId, animalId, formData) {
  return apiClient.post(`/farms/${farmId}/animals/${animalId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export function deleteAnimalPhoto(farmId, animalId, photoId) {
  return apiClient.delete(`/farms/${farmId}/animals/${animalId}/photos/${photoId}`);
}

export function identifyFromPhoto(formData) {
  return apiClient.post('/animals/identify-from-photo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}
