import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'create_sale.csv');
const cases = readCsv<{
  test_id: string;
  intent: string;
  product_name: string;
  price: string;
  quantity: string;
  unit: string;
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
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_token';
    }

    const payload: Record<string, any> = {
      intent: tc.intent,
      text: `Bán ${tc.quantity} ${tc.unit} ${tc.product_name} giá ${tc.price}`,
    };

    if (tc.product_name !== '<MISSING>') payload.product = tc.product_name;
    if (tc.price !== '<MISSING>') payload.price = isNaN(Number(tc.price)) ? tc.price : Number(tc.price);
    if (tc.quantity !== '<MISSING>') payload.quantity = isNaN(Number(tc.quantity)) ? tc.quantity : Number(tc.quantity);
    if (tc.unit !== '<MISSING>') payload.unit = tc.unit;

    if (tc.expected === '201' && authToken && payload.product) {
      await request.post(TRANSACTION_ENDPOINT, {
        headers,
        data: {
          intent: 'mua_hang',
          product: payload.product,
          quantity: 10,
          price: 50000,
          unit: payload.unit || 'lon',
          text: `Nhập tồn kho 10 ${payload.unit || 'lon'} ${payload.product}`,
        },
      });
    }

    const res = await request.post(TRANSACTION_ENDPOINT, {
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
        feature: 'Transactions - Create Sale (Bán hàng)',
        summary: tc.note,
        endpoint: TRANSACTION_ENDPOINT,
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Tạo giao dịch bán hàng phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_TRANSACTION_CREATE_SALE.md');
  }
});
