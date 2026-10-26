import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';

const csvFilePath = path.join(__dirname, 'login.csv');
const cases = readCsv<{
  test_id: string;
  email: string;
  password: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const LOGIN_ENDPOINT = process.env.LOGIN_ENDPOINT || '/api/v1/auth/login';

const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const payload = { email: tc.email, password: tc.password };

    const res = await request.post(LOGIN_ENDPOINT, {
      data: payload,
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
        feature: 'Auth - Login',
        summary: tc.note,
        endpoint: LOGIN_ENDPOINT,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Đăng nhập phản hồi HTTP ${res.status()} khác với mong đợi ${expectedStatus}.`,
      });
    }

    const failureMessage = [
      `\n❌ TESTCASE FAILED: [${tc.test_id}] ${tc.note}`,
      `• Endpoint:        ${LOGIN_ENDPOINT}`,
      `• Input:           email="${tc.email}", password="${tc.password}"`,
      `• Expected Status: ${expectedStatus}`,
      `• Actual Status:   ${res.status()}`,
      `• Response Body:   ${JSON.stringify(body, null, 2)}`,
    ].join('\n');

    expect(res.status(), failureMessage).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_AUTH_LOGIN.md');
  }
});
