import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'pay_supplier_debt.csv');
const cases = readCsv<{
  test_id: string;
  supplier_id: string;
  account_id: string;
  amount: string;
  note: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note_tc: string;
}>(csvFilePath);

// POST /api/v1/suppliers/{supplier_id}/debt-payments (thanh toán FIFO)
const PAY_SUPPLIER_DEBT_ENDPOINT = (supplierId: unknown) => `/api/v1/suppliers/${supplierId}/debt-payments`;

let authToken = '';
let targetSupplierId = 270002;
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  authToken = await getAuthToken(request);
  if (authToken) {
    try {
      const res = await request.get('/api/v1/suppliers', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      const list = data?.data || data?.suppliers || (Array.isArray(data) ? data : []);
      if (list.length > 0 && list[0].supplier_id) {
        targetSupplierId = list[0].supplier_id;
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

    const supplierIdToUse = tc.supplier_id === 'EXISTING_ID' ? targetSupplierId : Number(tc.supplier_id);

    const payload = {
      supplier_id: supplierIdToUse,
      account_id: Number(tc.account_id) || 1,
      amount: isNaN(Number(tc.amount)) ? tc.amount : Number(tc.amount),
      note: tc.note,
    };

    if (tc.expected === '200' && authToken) {
      await request.post(`/api/v1/suppliers/${supplierIdToUse}/debts`, {
        headers,
        data: {
          supplier_id: supplierIdToUse,
          total_debt: 500000,
          note: 'Khoản nợ chuẩn bị để test trả nợ',
        },
      });
    }

    const res = await request.post(PAY_SUPPLIER_DEBT_ENDPOINT(supplierIdToUse), {
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
          url: PAY_SUPPLIER_DEBT_ENDPOINT(supplierIdToUse),
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
        feature: 'Debts - Pay Supplier Debt',
        summary: tc.note_tc,
        endpoint: PAY_SUPPLIER_DEBT_ENDPOINT(supplierIdToUse),
        headers,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Trả nợ nhà cung cấp phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note_tc} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_DEBT_SUPPLIER_PAY.md');
  }
});
