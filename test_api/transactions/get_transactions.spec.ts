import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'get_transactions.csv');
const cases = readCsv<{
  test_id: string;
  intent_filter: string;
  intent_type: string;
  page: string;
  limit: string;
  raw_query: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const TRANSACTION_ENDPOINT = process.env.TRANSACTION_ENDPOINT || '/api/v1/transactions';

let authToken = '';
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const headers: Record<string, string> = {};

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_token';
    }

    let url = TRANSACTION_ENDPOINT;
    if (tc.raw_query) {
      url = `${TRANSACTION_ENDPOINT}?${tc.raw_query}`;
    } else {
      const params = new URLSearchParams();
      if (tc.page) params.append('page', tc.page);
      if (tc.limit) params.append('limit', tc.limit);
      if (tc.intent_filter) params.append('intent', tc.intent_filter);
      if (tc.intent_type) params.append('intent_type', tc.intent_type);
      const queryString = params.toString();
      if (queryString) {
        url = `${TRANSACTION_ENDPOINT}?${queryString}`;
      }
    }

    const res = await request.get(url, { headers });
    const text = await res.text();
    let body: any = text;
    try {
      body = JSON.parse(text);
    } catch {}

    await test.info().attach('response', {
      body: JSON.stringify(
        {
          test_id: tc.test_id,
          note: tc.note,
          url,
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
        feature: 'Transactions - Get Transactions',
        summary: tc.note,
        endpoint: url,
        headers,
        payload: {},
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Lấy danh sách giao dịch phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);

    // Kiểm tra đặc thù cho case cả 2 tham số cùng sai
    if (tc.test_id === 'TC_TX01_018' && isPassed && typeof body === 'object' && body !== null) {
      const details = (body as { detail?: unknown[] }).detail;
      expect(Array.isArray(details) && details.length >= 2, 'Body phải có đủ 2 lỗi validation').toBe(true);
    }
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_TRANSACTION_GET_ALL.md');
  }
});
