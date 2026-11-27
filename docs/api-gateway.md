# API Gateway trong lab này

App dùng một HTTP API. Mỗi request ảnh đi qua năm việc dưới đây.

Endpoint: `https://mx8g8jo987.execute-api.ap-southeast-1.amazonaws.com`

Lambda: `gha-lambda-practice-images`

## Đang làm

- Nhận HTTP tại endpoint ở trên.
- Khớp sáu route:
  - `POST /images`
  - `POST /images/{id}/complete`
  - `GET /images`
  - `GET /images/{id}`
  - `PATCH /images/{id}`
  - `DELETE /images/{id}`
- Kiểm tra chữ ký IAM trên cả sáu route.
- Đưa nguyên request sang Lambda, payload format 1.0.
- Phát hành ở stage `$default`, tự cập nhật khi Terraform đổi route.

## Chưa làm

Cùng loại HTTP API, request của lab không đụng tới:

- JWT authorizer và Lambda authorizer.
- CORS.
- Giới hạn số request.
- Access log.
- Payload format 2.0.
- Đổi header hoặc body trước khi vào Lambda.
- Domain riêng.
- mTLS.
- VPC Link.
- WAF.
- Stage thứ hai, ngoài `$default`.
- Route `PUT` và `OPTIONS`. Hai method đó chỉ có trên dropdown của tab HTTP.

Loại API khác, Terraform không tạo:

- REST API: mock, gọi thẳng S3, SQS hay DynamoDB, API key, usage plan, kiểm tra body, cache, canary, endpoint private.
- WebSocket API: `$connect`, `$disconnect`, `$default`. Tab WebSocket chỉ là client, không có server phía sau.
