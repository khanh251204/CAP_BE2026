import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'create_product.csv');
const cases = readCsv<{
  test_id: string;
  product_name: string;
  product_type: string;
  default_unit: string;
  unit_price: string;
  min_quantity: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const PRODUCT_ENDPOINT = process.env.PRODUCT_ENDPOINT || '/api/v1/products';

let authToken = '';
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const payload: Record<string, any> = {};

    if (tc.product_name !== '<MISSING>') {
      let name = tc.product_name === '<NULL>' ? null : tc.product_name;
      if (name && tc.expected === '201') {
        name = `${name} ${Date.now()}`;
      }
      payload.product_name = name;
    }

    if (tc.product_type !== '<MISSING>') {
      payload.product_type = tc.product_type === '<NULL>' ? null : tc.product_type;
    }

    if (tc.default_unit !== '<MISSING>') {
      payload.default_unit = tc.default_unit === '<NULL>' ? null : tc.default_unit;
    }

    if (tc.unit_price !== '<MISSING>') {
      if (tc.unit_price === '<NULL>') {
        payload.unit_price = null;
      } else if (tc.unit_price !== '' && !isNaN(Number(tc.unit_price))) {
        payload.unit_price = Number(tc.unit_price);
      } else {
        payload.unit_price = tc.unit_price;
      }
    }

    if (tc.min_quantity !== '<MISSING>') {
      if (tc.min_quantity === '<NULL>') {
        payload.min_quantity = null;
      } else if (tc.min_quantity !== '' && !isNaN(Number(tc.min_quantity))) {
        payload.min_quantity = Number(tc.min_quantity);
      } else {
        payload.min_quantity = tc.min_quantity;
      }
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    const isNoAuth = tc.note.includes('[NO_TOKEN]');
    const isInvalidAuth = tc.note.includes('[INVALID_TOKEN]');
    const isMalformedAuth = tc.note.includes('[MALFORMED_TOKEN]');

    if (isInvalidAuth) {
      headers['Authorization'] = 'Bearer invalid_or_expired_token_12345';
    } else if (isMalformedAuth) {
      headers['Authorization'] = 'Bearer this_is_not_a_valid_jwt';
    } else if (!isNoAuth && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const res = await request.post(PRODUCT_ENDPOINT, {
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
        feature: 'Products - Create Product',
        summary: tc.note,
        endpoint: PRODUCT_ENDPOINT,
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Thêm sản phẩm phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    const failureMessage = [
      `\n❌ TESTCASE FAILED: [${tc.test_id}] ${tc.note}`,
      `• Endpoint: ${PRODUCT_ENDPOINT}`,
      `• Payload:  ${JSON.stringify(payload)}`,
      `• Expected: ${expectedStatus}`,
      `• Actual:   ${res.status()}`,
      `• Response: ${JSON.stringify(body, null, 2)}`,
    ].join('\n');

    expect(res.status(), failureMessage).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_PRODUCT_CREATE.md');
  }
});
