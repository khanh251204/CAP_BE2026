import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'update_product.csv');
const cases = readCsv<{
  test_id: string;
  product_id: string;
  product_name: string;
  unit_price: string;
  default_unit: string;
  forbidden_field?: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const PRODUCTS_ENDPOINT = process.env.PRODUCT_ENDPOINT || '/api/v1/products';

let authToken = '';
let sampleProductId = 1;
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);

  if (authToken) {
    try {
      const listRes = await request.get(PRODUCTS_ENDPOINT, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const listData = await listRes.json();
      const items = listData?.data || listData;
      if (Array.isArray(items) && items.length > 0) {
        sampleProductId = items[0].product_id || items[0].id || 1;
      }
    } catch {}
  }
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_or_expired_token';
    }

    const payload: Record<string, any> = {
      product_name: tc.product_name,
      default_unit: tc.default_unit,
    };

    if (tc.unit_price && !isNaN(Number(tc.unit_price))) {
      payload.unit_price = Number(tc.unit_price);
    } else if (tc.unit_price) {
      payload.unit_price = tc.unit_price;
    }

    if (tc.forbidden_field) {
      payload[tc.forbidden_field] = 100;
    }

    const idToUse = tc.product_id === 'EXISTING_ID' ? sampleProductId : tc.product_id;
    const url = `${PRODUCTS_ENDPOINT}/${idToUse}`;

    const res = await request.put(url, {
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
          note: tc.note,
          url,
          request_payload: payload,
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
        feature: 'Products - Update Product',
        summary: tc.note,
        endpoint: url,
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Sửa sản phẩm phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_PRODUCT_UPDATE.md');
  }
});
