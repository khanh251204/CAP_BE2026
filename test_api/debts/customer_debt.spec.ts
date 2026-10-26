import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'customer_debt.csv');
const cases = readCsv<{
  test_id: string;
  customer_id: string;
  total_debt: string;
  note: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note_tc: string;
}>(csvFilePath);

// POST /api/v1/customers/{customer_id}/debts
const DEBT_CUSTOMER_ENDPOINT = (customerId: unknown) => `/api/v1/customers/${customerId}/debts`;

let authToken = '';
let targetCustomerId = 240002;
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);
  if (authToken) {
    try {
      const res = await request.get('/api/v1/customers', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      const list = data?.data || data?.customers || (Array.isArray(data) ? data : []);
      if (list.length > 0 && list[0].customer_id) {
        targetCustomerId = list[0].customer_id;
      }
    } catch {}
  }
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note_tc}`, async ({ request }) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_token';
    }

    const customerIdToUse = tc.customer_id === 'EXISTING_ID' ? targetCustomerId : Number(tc.customer_id);

    const payload = {
      customer_id: customerIdToUse,
      total_debt: isNaN(Number(tc.total_debt)) ? tc.total_debt : Number(tc.total_debt),
      note: tc.note,
    };

    const res = await request.post(DEBT_CUSTOMER_ENDPOINT(customerIdToUse), {
      data: payload,
      headers,
    });

    const text = await res.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {}

    await test.info().attach('response', {
      body: JSON.stringify(
        {
          test_id: tc.test_id,
          note: tc.note_tc,
          url: DEBT_CUSTOMER_ENDPOINT(customerIdToUse),
          actual_status: res.status(),
          expected_status: tc.expected,
          response_body: body,
        },
        null,
        2
      ),
      contentType: 'application/json',
    });

    const expectedStatus = Number(tc.expected.match(/\d{3}/)?.[0] || tc.expected);
    const isPassed = res.status() === expectedStatus;

    actualResults.set(
      tc.test_id,
      isPassed
        ? `Status ${res.status()} (PASSED)`
        : `Status ${res.status()} (FAILED: Expected ${expectedStatus})`
    );

    if (!isPassed) {
      defects.push({
        testId: tc.test_id,
        feature: 'Debts - Create Customer Debt',
        summary: tc.note_tc,
        endpoint: DEBT_CUSTOMER_ENDPOINT(customerIdToUse),
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Tạo công nợ khách hàng phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note_tc} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_DEBT_CUSTOMER_CREATE.md');
  }
});
