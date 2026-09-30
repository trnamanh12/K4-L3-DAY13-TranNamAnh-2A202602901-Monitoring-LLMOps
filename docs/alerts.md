# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests`, SLO latency tối đa 3,000 ms; alert cảnh báo sớm ở 2,000 ms.
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 2000 ms` trong 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời chậm hơn baseline; nếu tiếp tục vượt 3,000 ms, request không đạt SLO.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận P95/P99 và TTFT P95 trong dashboard, giữ cùng time range 60 phút.
  2. Lọc `response_sent` trong `data/logs.jsonl`, lấy request có latency cao và `correlation_id`.
  3. Mở trace tương ứng trên Langfuse, so sánh thời lượng retrieval với generation.
- Mitigation tạm thời: rollback prompt production nếu generation tăng bất thường; nếu retrieval chậm, tắt practice scenario hoặc khôi phục dịch vụ retrieval.
- Owner: `student-2A202602901`

## Alert 2

- Tên: `RequestErrorsOrRetrievalFailures`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate tối đa 2%; retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: `error_rate > 2%` hoặc `retrieval_success_rate < 90%` trong 5 phút.
- Ảnh hưởng tới người dùng: request có thể thất bại hoặc câu trả lời thiếu ngữ cảnh truy xuất.
- Ba bước kiểm tra đầu tiên:
  1. So sánh `request_failed` với `request_received`, rồi kiểm tra retrieval success trên dashboard.
  2. Nhóm log lỗi theo `error_type`, lấy correlation ID của một request thất bại.
  3. Mở trace cùng correlation ID và kiểm tra trạng thái/span retrieval.
- Mitigation tạm thời: tắt practice scenario nếu đang bật; khôi phục retrieval; nếu retrieval vẫn lỗi, thông báo sự cố và dùng fallback phù hợp.
- Owner: `student-2A202602901`

## Alert 3

- Tên: `DailyCostBudget`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail chi phí tối đa 2.50 USD mỗi ngày.
- Điều kiện và thời gian duy trì: tổng `response_sent.cost_usd` trong ngày lớn hơn 2.50 USD liên tục trong 10 phút.
- Ảnh hưởng tới người dùng: chi phí vận hành tăng nhanh ngoài ngân sách dự kiến.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra tổng cost và cost theo phút trong dashboard, xác nhận khoảng thời gian và đơn vị USD.
  2. Lọc `response_sent` theo ngày, so sánh cost với `tokens_in`/`tokens_out` và model.
  3. Mở các trace có cost cao, xác định prompt/version và request pattern gây tăng token.
- Mitigation tạm thời: rollback prompt nếu version mới làm tăng tokens; giảm workload demo hoặc tắt cost-spike practice scenario.
- Owner: `student-2A202602901`
