# DataGuard

DataGuard is a CSV data-quality checker. The frontend is plain HTML, CSS, and
JavaScript. The backend is designed for AWS Lambda, S3, API Gateway, and
CloudWatch. No AWS resources are created by this project automatically.

## What is already configured

- `frontend/`: responsive dashboard based on the supplied design
- `backend/validator.py`: reusable CSV validation engine
- `backend/api_handler.py`: presigned upload URL, job status, and report APIs
- `backend/validator_handler.py`: S3-triggered CSV processor
- `backend/report_builder.py`: report metadata builder
- Optional SNS summary email notifications after every processed upload
- `template.yaml`: AWS SAM infrastructure with private encrypted S3 storage
- `sample_data/`: valid and intentionally invalid employee CSV files
- `backend/tests/`: offline unit tests

The initial schema is defined in [backend/config.py](backend/config.py):
`employee_id` is a required integer, `name` is a required string, `age` is an
optional integer, `salary` is an optional positive decimal, and `email` is an
optional string.

## Optional SNS email notifications

The template now creates an SNS topic and an email subscription. During
CloudFormation deployment, enter your email in the `NotificationEmail`
parameter. AWS sends a confirmation message; click **Confirm subscription**
before testing. The validator publishes a summary after every processed file.
It does not include issue values or the full CSV report in email. The detailed
JSON remains in S3.

SNS email delivery requires an active subscription and may be subject to AWS
service limits or charges. To disable notifications, remove the SNS resources,
the validator `sns:Publish` permission, and `SNS_TOPIC_ARN` before redeploying.

## Local setup

Run these commands from the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m http.server 5500 --directory frontend
```

Open `http://localhost:5500`. The dashboard can be viewed locally now. AWS
upload buttons work only after deployment and API configuration.

## AWS prerequisites

Install and configure these manually:

1. AWS CLI, then run `aws configure` with your own credentials. Never put keys
   in this repository.
2. AWS SAM CLI.
3. Docker Desktop if using `sam build --use-container`.
4. An AWS region selected by you, such as `us-east-1`.

Verify:

```powershell
aws sts get-caller-identity
sam --version
```

The deploying identity needs permission to create the resources in
`template.yaml`, including CloudFormation, Lambda, API Gateway, S3, IAM roles,
and CloudWatch log groups. For a learning account, use an approved deployment
role or the AWS SAM guided deployment flow; do not paste credentials into code.
The generated Lambda roles are least-privilege for runtime:

- API Lambda: presigned `PutObject` to `incoming/*`, `HeadObject`/`GetObject`
  for incoming and report objects, and a scoped `ListBucket` for incoming and
  report job prefixes.
- Validator Lambda: `GetObject` from `incoming/*` and `PutObject` to
  `reports/*`.
- S3 invokes only the validator for `incoming/*.csv`, so report writes cannot
  recursively invoke it.

## Build and deploy manually

Review the resource and cost list before deployment:

- One private S3 bucket with AES-256 encryption
- Two Lambda functions
- One API Gateway API
- CloudWatch log groups
- IAM execution roles

S3 storage, Lambda requests/duration, API Gateway requests, CloudWatch logs,
and data transfer can incur charges. Check current AWS pricing and free-tier
limits for your region.

Build and validate without deploying:

```powershell
sam validate --lint
sam build
```

When you are ready, deploy manually:

```powershell
sam deploy --guided
```

Choose your AWS region. Accept the generated stack name and allow SAM to create
the required IAM roles when prompted. Do not use `--capabilities
CAPABILITY_IAM` without understanding that it permits role creation.

After deployment, copy the `ApiEndpoint` and `DataBucketName` outputs:

```powershell
aws cloudformation describe-stacks --stack-name <your-stack-name> `
  --query "Stacks[0].Outputs"
```

## Configure the frontend manually

Open [frontend/config.js](frontend/config.js) and replace the empty API URL:

```js
window.DATAGUARD_CONFIG = {
  apiBaseUrl: "https://REPLACE_WITH_ApiEndpoint",
  maxFileSizeBytes: 10 * 1024 * 1024,
  pollIntervalMs: 3000,
  demoMode: false
};
```

Use the complete `ApiEndpoint` value from the SAM output, without adding a
trailing slash. The API currently allows CORS from all origins for learning
and local testing. Before public use, change `AllowOrigin` in
[template.yaml](template.yaml) to the exact frontend origin, redeploy, and
host the frontend securely (for example, private S3 behind CloudFront).

Run the frontend again:

```powershell
python -m http.server 5500 --directory frontend
```

Select a CSV, upload it, and wait for the real report status. The browser
uploads directly to S3 using a short-lived presigned URL; it never receives
AWS credentials.

The S3 bucket includes CORS rules for `http://localhost:5500` and
`http://127.0.0.1:5500`, which are required for browser uploads to a presigned
URL. If you use another frontend origin, add it to `CorsConfiguration` in
`template.yaml`, then rebuild and update the CloudFormation stack.

## Troubleshooting

- **CORS error:** verify `apiBaseUrl` and the API `AllowOrigin` setting.
- **403 on upload:** the presigned URL may be expired or the content type
  header may differ; request a fresh URL and do not alter its headers.
- **Status remains WAITING:** confirm the upload reached the incoming prefix
  and that the validator Lambda has an S3 trigger.
- **FAILED report:** inspect the validator Lambda CloudWatch log group.
- **SAM permission error:** use an approved deployment role with CloudFormation,
  IAM, Lambda, API Gateway, S3, and CloudWatch permissions.
- **No report:** check that the validator can read `incoming/*` and write
  `reports/*`.

## Cleanup

Delete uploaded objects first because S3 buckets must be empty:

```powershell
aws s3 rm s3://<DataBucketName>/incoming/ --recursive
aws s3 rm s3://<DataBucketName>/reports/ --recursive
sam delete --stack-name <your-stack-name> --region <your-region>
```

Confirm the stack, bucket, Lambda functions, API, log groups, and IAM roles
were removed. Keep `.venv` for local work or remove that specific directory
when no longer needed.

## Limitations

This first version has no authentication or per-user authorization and is
intended for a controlled demonstration. Status is inferred from S3 object
existence, so a separate job database would be more reliable for production.
The next improvements should include authentication, a job table, stronger
CSV schema selection, and a private frontend hosted behind CloudFront.
