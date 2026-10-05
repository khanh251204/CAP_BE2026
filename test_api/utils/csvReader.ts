import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';

/**
 * Đọc file CSV an toàn không trim để giữ nguyên khoảng trắng
 * @param filePath Đường dẫn tương đối hoặc tuyệt đối tới file CSV
 */
export function readCsv<T = Record<string, string>>(filePath: string): T[] {
  const resolvedPath = path.isAbsolute(filePath)
    ? filePath
    : path.resolve(__dirname, filePath);

  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`[csvReader] Không tìm thấy file CSV tại: ${resolvedPath}`);
  }

  const rawContent = fs.readFileSync(resolvedPath, 'utf-8');
  return parse(rawContent, {
    columns: true,
    skip_empty_lines: true,
  });
}

/**
 * Cập nhật cột actual vào file CSV sau khi chạy test xong
 * @param filePath Đường dẫn tới file CSV
 * @param results Map lưu test_id -> chuỗi kết quả actual (VD: "Status 200 (PASSED)")
 */
export function updateCsvActual(
  filePath: string,
  results: Map<string, string>
): void {
  const resolvedPath = path.isAbsolute(filePath)
    ? filePath
    : path.resolve(__dirname, filePath);

  if (!fs.existsSync(resolvedPath)) return;

  const rawContent = fs.readFileSync(resolvedPath, 'utf-8');
  const records = parse(rawContent, {
    columns: true,
    skip_empty_lines: true,
  }) as Record<string, string>[];

  if (records.length === 0) return;

  const headers = Object.keys(records[0]);
  if (!headers.includes('actual')) {
    // Nếu chưa có cột actual thì thêm vào trước cột note hoặc ở cuối
    const noteIdx = headers.indexOf('note');
    if (noteIdx !== -1) {
      headers.splice(noteIdx, 0, 'actual');
    } else {
      headers.push('actual');
    }
  }

  const escapeCsv = (val: any) => {
    const s = String(val ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };

  const lines: string[] = [headers.join(',')];

  for (const row of records) {
    const testId = row.test_id;
    if (results.has(testId)) {
      row.actual = results.get(testId)!;
    }
    const rowValues = headers.map((h) => escapeCsv(row[h]));
    lines.push(rowValues.join(','));
  }

  fs.writeFileSync(resolvedPath, lines.join('\n'), 'utf-8');
}
