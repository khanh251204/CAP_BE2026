import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'pay_customer_debt.csv');
const cases = readCsv<{
  test_id: string;
  customer_id: string;
  account_id: string;
  amount: string;
  note: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note_tc: string;
}>(csvFilePath);

const COLLECT_DEBT_ENDPOINT = process.env.COLLECT_DEBT_ENDPOINT || '/api/v1/debts/customer/payments';

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
      account_id: Number(tc.account_id) || 1,
      amount: isNaN(Number(tc.amount)) ? tc.amount : Number(tc.amount),
      note: tc.note,
    };

    if (tc.expected === '200' && authToken) {
      await request.post('/api/v1/debts/customer', {
        headers,
        data: {
          customer_id: customerIdToUse,
          total_debt: 500000,
          note: 'Khoản nợ chuẩn bị để test thu nợ',
        },
      });
    }

    const res = await request.post(COLLECT_DEBT_ENDPOINT, {
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
          url: COLLECT_DEBT_ENDPOINT,
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
        feature: 'Debts - Pay Customer Debt',
        summary: tc.note_tc,
        endpoint: COLLECT_DEBT_ENDPOINT,
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Thu tiền nợ khách hàng phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note_tc} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_DEBT_CUSTOMER_PAY.md');
  }
});
