import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'get_products.csv');
const cases = readCsv<{
  test_id: string;
  query_param: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const PRODUCTS_ENDPOINT = process.env.PRODUCT_ENDPOINT || '/api/v1/products';

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
      headers['Authorization'] = 'Bearer invalid_or_expired_token';
    }

    let url = PRODUCTS_ENDPOINT;
    if (tc.query_param) {
      url = `${PRODUCTS_ENDPOINT}/search?name=${encodeURIComponent(tc.query_param)}`;
    }

    const res = await request.get(url, { headers });
    const text = await res.text();
    let body: unknown = text;
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
        feature: 'Products - Get Products',
        summary: tc.note,
        endpoint: url,
        headers,
        payload: {},
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Lấy danh sách sản phẩm phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_PRODUCT_GET_ALL.md');
  }
});
