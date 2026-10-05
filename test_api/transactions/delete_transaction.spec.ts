import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'delete_transaction.csv');
const cases = readCsv<{
  test_id: string;
  transaction_id: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const TRANSACTION_ENDPOINT = process.env.TRANSACTION_ENDPOINT || '/api/v1/transactions';

let authToken = '';
let targetTxIdToDelete = 0;
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);

  if (authToken) {
    try {
      const createRes = await request.post(TRANSACTION_ENDPOINT, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        data: {
          intent: 'ban_hang',
          text: 'Bán 1 lon nước ngọt test xóa 10000',
          product: 'Coca Cola 330ml',
          price: 10000,
          quantity: 1,
          unit: 'lon',
        },
      });
      const data = await createRes.json();
      targetTxIdToDelete = data?.data?.transaction_id || data?.data?.id || 0;
    } catch {}
  }
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const headers: Record<string, string> = {};

    if (tc.auth_type === 'VALID' && authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    } else if (tc.auth_type === 'INVALID_TOKEN') {
      headers['Authorization'] = 'Bearer invalid_token';
    }

    let idToUse = tc.transaction_id;
    if (tc.transaction_id === 'NEW_TX_ID' && authToken) {
      try {
        const createRes = await request.post(TRANSACTION_ENDPOINT, {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          data: {
            intent: 'mua_hang',
            product: 'Banh Snack Oishi',
            quantity: 5,
            price: 25000,
            unit: 'goi',
            text: 'Mua 5 goi Banh Snack Oishi gia 25000',
          },
        });
        const createdData = await createRes.json();
        idToUse = String(
          createdData?.data?.transaction_id ||
          createdData?.transaction_id ||
          targetTxIdToDelete ||
          99999999
        );
      } catch {
        idToUse = '99999999';
      }
    }

    const url = `${TRANSACTION_ENDPOINT}/${idToUse}`;

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
        feature: 'Transactions - Delete Transaction',
        summary: tc.note,
        endpoint: url,
        headers,
        payload: {},
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Xóa giao dịch phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_TRANSACTION_DELETE.md');
  }
});
