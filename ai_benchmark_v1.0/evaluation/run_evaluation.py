# evaluation/run_evaluation.py
import argparse
import sys
import os

# Đảm bảo đường dẫn gốc được đưa vào sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from evaluation.evaluator import NLPEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="VoiceCashBook NLP Evaluation with Groq")
    parser.add_argument(
        "--csv",
        type=str,
        default="evaluation/voicecash_producer_1000.csv",
        help="Đường dẫn tới file CSV test dataset (mặc định: evaluation/voicecash_producer_1000.csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số lượng mẫu chạy đánh giá (bỏ trống để chạy toàn bộ dataset)",
    )
    parser.add_argument(
        "--cache",
        type=str,
        default="evaluation/groq_predictions_cache.json",
        help="File lưu cache kết quả dự đoán của Groq để tránh gọi lại API",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="evaluation/evaluation_report.md",
        help="File xuất báo cáo Markdown (mặc định: evaluation/evaluation_report.md)",
    )
    parser.add_argument(
        "--predictions-csv",
        type=str,
        default="evaluation/predictions.csv",
        help="File xuất chi tiết so sánh true vs predicted (mặc định: evaluation/predictions.csv)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Tên mô hình Groq (mặc định: sử dụng mô hình trong groq_service.py)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Thời gian nghỉ (giây) giữa các request API để tránh chạm rate limit",
    )
    return parser.parse_args()


def main():
    # Cấu hình encoding stdout để in tiếng Việt chuẩn xác trên Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    evaluator = NLPEvaluator(
        csv_path=args.csv,
        cache_path=args.cache,
        model_name=args.model,
        delay_seconds=args.delay,
    )

    results = evaluator.run_evaluation(
        limit=args.limit,
        save_predictions_csv=args.predictions_csv,
    )

    evaluator.print_summary(results)
    evaluator.save_markdown_report(results, output_file=args.report)


if __name__ == "__main__":
    main()
