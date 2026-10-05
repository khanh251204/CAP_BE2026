import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';
import { getAuthToken } from '../utils/authHelper';

const csvFilePath = path.join(__dirname, 'expense.csv');
const cases = readCsv<{
  test_id: string;
  period_type: string;
  date: string;
  year: string;
  month: string;
  quarter: string;
  from_date: string;
  to_date: string;
  auth_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const EXPENSE_ENDPOINT = process.env.EXPENSE_ENDPOINT || '/api/v1/reports/expenses';

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
      headers['Authorization'] = 'Bearer invalid_token_xyz';
    }

    const params = new URLSearchParams();
    if (tc.period_type) params.append('period_type', tc.period_type);
    if (tc.date) params.append('date', tc.date);
    if (tc.year) params.append('year', tc.year);
    if (tc.month) params.append('month', tc.month);
    if (tc.quarter) params.append('quarter', tc.quarter);
    if (tc.from_date) params.append('from', tc.from_date);
    if (tc.to_date) params.append('to', tc.to_date);

    const queryString = params.toString();
    const url = queryString ? `${EXPENSE_ENDPOINT}?${queryString}` : EXPENSE_ENDPOINT;

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
        feature: 'Reports - Expense',
        summary: tc.note,
        endpoint: url,
        headers,
        payload: Object.fromEntries(params.entries()),
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Báo cáo Chi phí phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    expect(res.status(), `[${tc.test_id}] ${tc.note} failed`).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_REPORT_EXPENSE.md');
  }
});
