import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'delete_product.csv');
const cases = readCsv<{
  test_id: string;
  product_id: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const PRODUCTS_ENDPOINT = process.env.PRODUCT_ENDPOINT || '/api/v1/products';

let authToken = '';
let targetProductIdToDelete = 0;
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);

  // Tạo 1 sản phẩm tạm thời để test xóa an toàn
  if (authToken) {
    try {
      const createRes = await request.post(PRODUCTS_ENDPOINT, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        data: {
          product_name: `Temp Delete Test Product ${Date.now()}`,
          product_type: 'RESALE',
          default_unit: 'cai',
          unit_price: 1000,
          min_quantity: 0,
        },
      });
      const createdData = await createRes.json();
      targetProductIdToDelete = createdData?.data?.product_id || 0;
    } catch {}
  }
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const headers: Record<string, string> = {};

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_or_expired_token';
    }

    let idToUse = tc.product_id;
    if (tc.product_id === 'NEW_CREATED_ID' && authToken) {
      try {
        const createRes = await request.post(PRODUCTS_ENDPOINT, {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          data: {
            product_name: `Temp Delete Test Product ${Date.now()}`,
            product_type: 'RESALE',
            default_unit: 'cai',
            unit_price: 1000,
            min_quantity: 0,
          },
        });
        const createdData = await createRes.json();
        idToUse = String(createdData?.data?.product_id || 99999999);
      } catch {
        idToUse = '99999999';
      }
    } else if (tc.product_id === 'EXISTING_ID') {
      idToUse = String(targetProductIdToDelete || 99999999);
    }

    const url = `${PRODUCTS_ENDPOINT}/${idToUse}`;

    const res = await request.delete(url, { headers });
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
        feature: 'Products - Delete Product',
        summary: tc.note,
        endpoint: url,
        headers,
        payload: {},
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Xóa sản phẩm phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_PRODUCT_DELETE.md');
  }
});
