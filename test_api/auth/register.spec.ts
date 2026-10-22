import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';

const csvFilePath = path.join(__dirname, 'register.csv');
const cases = readCsv<{
  test_id: string;
  fullName: string;
  email: string;
  password: string;
  accountType: string;
  province: string;
  storeName?: string;
  businessField?: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const REGISTER_ENDPOINT = process.env.REGISTER_ENDPOINT || '/api/v1/register';

const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const payload: Record<string, any> = {};

    // Gắn timestamp cho các ca tạo mới thành công để tránh lỗi trùng email khi test lặp lại
    let emailToUse = tc.email;
    if (tc.expected === '201' && emailToUse.includes('@')) {
      const [namePart, domainPart] = emailToUse.split('@');
      emailToUse = `${namePart}_${Date.now()}@${domainPart}`;
    }

    if (tc.fullName !== '<MISSING>') payload.fullName = tc.fullName;
    if (tc.email !== '<MISSING>') payload.email = emailToUse;
    if (tc.password !== '<MISSING>') payload.password = tc.password;
    if (tc.accountType !== '<MISSING>') payload.accountType = tc.accountType;
    if (tc.province !== '<MISSING>') payload.province = tc.province;

    if (tc.storeName && tc.storeName !== '<MISSING>') {
      payload.storeName = tc.storeName;
    }
    if (tc.businessField && tc.businessField !== '<MISSING>') {
      payload.businessField = tc.businessField;
    }

    const res = await request.post(REGISTER_ENDPOINT, {
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
        feature: 'Auth - Register',
        summary: tc.note,
        endpoint: REGISTER_ENDPOINT,
        payload,
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Đăng ký phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    const failureMessage = [
      `\n❌ TESTCASE FAILED: [${tc.test_id}] ${tc.note}`,
      `• Endpoint:        ${REGISTER_ENDPOINT}`,
      `• Payload:         ${JSON.stringify(payload)}`,
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
    generateDefectReports(defects, 'Defect_Report_AUTH_REGISTER.md');
  }
});
