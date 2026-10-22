import fs from 'fs';
import path from 'path';

export interface DefectItem {
  testId: string;
  feature: string;
  summary: string;
  endpoint: string;
  headers?: Record<string, string>;
  payload: any;
  expectedStatus: number;
  actualStatus: number;
  responseBody: any;
  severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  priority?: 'LOW' | 'MEDIUM' | 'HIGH';
  tester?: string;
  explanation?: string;
  potentialRootCause?: string;
  suggestedFix?: string;
}

/**
 * Tự động tạo Defect Report theo chuẩn 13 mục QA/QC vào thư mục reports/defects/
 */
export function generateDefectReports(defects: DefectItem[], reportName?: string): string {
  if (defects.length === 0) return '';

  const defectsDir = path.resolve(__dirname, '../reports/defects');
  if (!fs.existsSync(defectsDir)) {
    fs.mkdirSync(defectsDir, { recursive: true });
  }

  const now = new Date();
  const dateFormatted = now.toLocaleDateString('vi-VN');
  const timestampStr = now.toISOString().replace(/[:.]/g, '-');
  const filename = reportName || `Defect_Report_${timestampStr}.md`;
  const targetFile = path.join(defectsDir, filename);

  let doc = `# DEFECT REPORT / BUG REPORT\n`;
  doc += `**QA/QC Documentation • Web Application & System Integration**\n\n`;
  doc += `*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*\n\n`;
  doc += `---\n\n`;

  defects.forEach((d, idx) => {
    const defectId = `BUG_${d.feature.toUpperCase().replace(/\s+/g, '_')}_${String(idx + 1).padStart(3, '0')}`;
    const severity = d.severity || (d.actualStatus >= 500 ? 'HIGH' : 'MEDIUM');
    const priority = d.priority || (d.actualStatus >= 500 ? 'HIGH' : 'MEDIUM');
    const tester = d.tester || 'Khánh Hoàng';

    doc += `## 1. PROJECT INFORMATION\n`;
    doc += `| Trường thông tin | Chi tiết |\n| :--- | :--- |\n`;
    doc += `| **Tên dự án (Project)** | VoiceCashBook / Web Platform |\n`;
    doc += `| **Tính năng (Feature)** | ${d.feature} |\n`;
    doc += `| **Người báo cáo (Tester)** | ${tester} |\n`;
    doc += `| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |\n`;
    doc += `| **Ngày tạo (Date)** | ${dateFormatted} |\n\n`;

    doc += `## 2. DEFECT INFORMATION\n`;
    doc += `| Trường thông tin | Chi tiết |\n| :--- | :--- |\n`;
    doc += `| **Defect ID** | **${defectId}** |\n`;
    doc += `| **Tiêu đề (Summary)** | [${d.testId}] ${d.summary} |\n`;
    doc += `| **Mức độ nghiêm trọng (Severity)** | **${severity}** |\n`;
    doc += `| **Độ ưu tiên (Priority)** | **${priority}** |\n`;
    doc += `| **Trạng thái (Status)** | **OPEN** |\n`;
    doc += `| **Người xử lý (Assignee)** | Dev Backend |\n`;
    doc += `| **Giải thích** | ${d.explanation || 'API phản hồi status code và dữ liệu không khớp với yêu cầu nghiệp vụ / contract.'} |\n\n`;

    doc += `## 3. DESCRIPTION\n`;
    doc += `Khi gọi API \`${d.endpoint}\` với testcase **${d.testId} - ${d.summary}**, kết quả trả về HTTP Status **${d.actualStatus}**, không đúng với mã kỳ vọng **${d.expectedStatus}**.\n\n`;

    doc += `## 4. STEPS TO REPRODUCE\n`;
    doc += `1. Chuẩn bị môi trường kiểm thử Backend.\n`;
    doc += `2. Gửi request POST tới endpoint \`${d.endpoint}\`.\n`;
    if (d.headers) {
      doc += `3. Headers:\n\`\`\`json\n${JSON.stringify(d.headers, null, 2)}\n\`\`\`\n`;
    }
    doc += `4. Request Payload:\n\`\`\`json\n${JSON.stringify(d.payload, null, 2)}\n\`\`\`\n\n`;

    doc += `## 5. EXPECTED RESULT\n`;
    doc += `API phản hồi HTTP Status Code: **${d.expectedStatus}**.\n\n`;

    doc += `## 6. ACTUAL RESULT\n`;
    doc += `- **HTTP Status Code thực tế**: **${d.actualStatus}**\n`;
    doc += `- **Response Body**:\n\`\`\`json\n${JSON.stringify(d.responseBody, null, 2)}\n\`\`\`\n\n`;

    doc += `## 7. POTENTIAL ROOT CAUSE\n`;
    doc += `⚠ **Suspected Root Cause**:\n`;
    doc += `${d.potentialRootCause || 'Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.'}\n\n`;

    doc += `## 8. API RESPONSE\n`;
    doc += `\`\`\`json\n${JSON.stringify(d.responseBody, null, 2)}\n\`\`\`\n`;
    doc += `- **HTTP Status**: ${d.actualStatus}\n`;
    doc += `- **Endpoint**: \`${d.endpoint}\`\n\n`;

    doc += `## 9. IMPACT (Business/User Impact)\n`;
    doc += `- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.\n`;
    doc += `- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.\n\n`;

    doc += `## 10. SUGGESTED FIX\n`;
    doc += `${d.suggestedFix || 'Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.'}\n\n`;

    doc += `## 11. ATTACHMENT & NOTES\n`;
    doc += `- Testcase ID: \`${d.testId}\`\n`;
    doc += `- Chi tiết Payload kiểm thử: \`${JSON.stringify(d.payload)}\`\n\n`;

    doc += `## 12. ACCEPTANCE CRITERIA / VERIFICATION\n`;
    doc += `☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **${d.expectedStatus}**.\n`;
    doc += `☐  Chạy lại kịch bản test Playwright \`${d.testId}\` đạt PASSED.\n\n`;

    doc += `## 13. DEFECT LIFECYCLE\n`;
    doc += `| Thuộc tính | Trạng thái |\n| :--- | :--- |\n`;
    doc += `| **Current Status** | Open |\n`;
    doc += `| **Next Action** | Developer investigate and fix API response handling |\n`;
    doc += `| **Retest Required** | Yes |\n`;
    doc += `| **Regression Test Required** | Yes |\n`;
    doc += `| **Reported by** | ${tester} |\n`;
    doc += `| **Date** | ${dateFormatted} |\n`;
    doc += `| **Status** | Open |\n\n`;
    doc += `---\n\n`;
  });

  fs.writeFileSync(targetFile, doc, 'utf-8');
  return targetFile;
}
