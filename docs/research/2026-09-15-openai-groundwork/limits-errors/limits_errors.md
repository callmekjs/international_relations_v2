# Limits, errors, refusals, data handling — verified quotes

Checked 2026-09-15 against official OpenAI docs (Markdown versions, `.md` suffix) and the official Python SDK `openai` 3.14.0 source. Every quote below was machine-checked to appear verbatim (whitespace-normalized) in the downloaded copy under `pages/` or `.venv/` (script: `scripts/build_limits_errors_md.py`). `|` inside quotes is escaped. Inferences are NOT in this table; see the end.


## 1. Spend control (budgets, projects)

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| S1 | Spend alert = notification only; hard spend limit = requests fail with 429 | "\| Spend alert \| Sends a notification; API traffic continues \| Track spend without interrupting traffic \|" | https://developers.openai.com/api/docs/guides/spend-limits |
| S1b | Hard limit must be switched on explicitly when setting the monthly limit (org and project) | "To make API responses fail after the project reaches the limit, turn on **Enforce a hard limit**." | https://developers.openai.com/api/docs/guides/spend-limits |
| S2 | Error returned when a hard limit is reached | "Reaching a project hard limit returns a `429` error with the `project_spend_limit_exceeded` code." | https://developers.openai.com/api/docs/guides/spend-limits |
| S2b | Org-level equivalent | "Reaching an organization hard limit returns a `429` error with the `organization_spend_limit_exceeded` code." | https://developers.openai.com/api/docs/guides/spend-limits |
| S3 | Enforcement delay caveat (overshoot possible, size not stated) | "Enforcement is not instantaneous. The API Platform can process a small amount of extra usage while the limit state propagates, so recorded spend can slightly exceed the configured amount." | https://developers.openai.com/api/docs/guides/spend-limits |
| S4 | OpenAI-assigned usage limit (by tier) is separate from limits you set | "OpenAI also assigns your organization an approved monthly [usage limit based on its usage tier](https://developers.openai.com/api/docs/guides/rate-limits#usage-tiers). This OpenAI-approved usage limit is separate from the spend limits you configure." | https://developers.openai.com/api/docs/guides/spend-limits |
| S5 | Project limit scope; org limit covers all projects | "A project hard limit applies only to API traffic billed to that project." | https://developers.openai.com/api/docs/guides/spend-limits |
| S5b | Other projects keep working when one project hits its limit | "Other projects can continue unless their own limit or the organization limit is also reached." | https://developers.openai.com/api/docs/guides/error-codes |
| S6 | Recovery: raise/remove limit (after propagation) or wait for monthly reset | "Raising or removing the reached limit allows traffic to resume after the update propagates. Otherwise, the limit resets with the next monthly cycle." | https://developers.openai.com/api/docs/guides/spend-limits |
| S7 | Separate projects for staging vs production, each with own rate and spend limits | "You can also limit user access to your production project, and set custom rate and spend limits per project." | https://developers.openai.com/api/docs/guides/production-best-practices |
| S7b | Project = boundary for keys and limits | "**Project**: A workspace for keys, files, and resources." | https://developers.openai.com/api/docs/guides/rbac |
| S8 | Project RPM/TPM can be lowered per model (cannot exceed org limit) | "A configured value can't exceed the limit available to the organization and project." | https://developers.openai.com/api/docs/guides/terraform/rate-limits-and-spend |
| S9 | Project model allowlist exists (dashboard/Terraform) | "`allow_list` to permit only the models in `model_ids`." | https://developers.openai.com/api/docs/guides/terraform/project-controls |
| S10 | Hard spend limits are new (changelog, July 22, 2026) | "Added hard spend limits for organizations and projects on the OpenAI API platform." | https://developers.openai.com/api/docs/changelog |

## 2. Error codes

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| E1 | Prepaid credits exhausted | "\| 429 - Credit balance exhausted \| **Code:** `credit_balance_exhausted` <br /> **Cause:** Your organization has no prepaid credits remaining." | https://developers.openai.com/api/docs/guides/error-codes |
| E2 | Ramp-rate throttle (type + code) | "\| 429 - Slow down \| **Type:** `rate_limit_error` <br /> **Code:** `slow_down`" | https://developers.openai.com/api/docs/guides/error-codes |
| E2b | OpenAI-assigned usage limit reached | "\| 429 - Organization usage limit reached \| **Code:** `organization_usage_limit_exceeded`" | https://developers.openai.com/api/docs/guides/error-codes |
| E2c | Model overload | "\| 503 - Model temporarily overloaded \| **Type:** `service_unavailable_error` <br /> **Code:** `server_is_overloaded`" | https://developers.openai.com/api/docs/guides/error-codes |
| E2d | Server error | "\| 500 - The server had an error while processing your request \| **Cause:** Issue on our servers. <br /> **Solution:** Retry your request after a brief wait" | https://developers.openai.com/api/docs/guides/error-codes |
| E2e | Unsupported region is 403 (no code documented) | "\| 403 - Country, region, or territory not supported \| **Cause:** You are accessing the API from an unsupported country, region, or territory." | https://developers.openai.com/api/docs/guides/error-codes |
| E3 | Billing errors: match error.code; error.type may still be insufficient_quota; never retry | "For billing-related errors, inspect `error.code` to identify the specific cause. The broader `error.type` can still be `insufficient_quota`. Retrying billing, spend, or quota errors won't restore API access." | https://developers.openai.com/api/docs/guides/error-codes |
| E4 | SDK exception classes for 429 vs 503 | "Python raises `RateLimitError` for `429` responses and `InternalServerError` for `503` responses." | https://developers.openai.com/api/docs/guides/error-codes |
| E5 | Context overflow is a 400 when truncation is disabled (default) | "`disabled` (default): If the input size will exceed the context window size for a model, the request will fail with a 400 error." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| E6 | In-response error codes (status=failed) include rate_limit_exceeded, server_error, bio_policy, misalignment_policy_violation | "`code: "server_error" or "rate_limit_exceeded" or "invalid_prompt" or 18 more`" | https://developers.openai.com/api/reference/resources/responses/methods/create |

## 3. Rate limits and retries

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| L1 | Usage tiers: Tier 1 needs $5 paid, usage limit $100/month | "\| Tier&nbsp;1 \| $5 paid \| $100 / month \|" | https://developers.openai.com/api/docs/guides/rate-limits |
| L1b | Tier 2 | "\| Tier&nbsp;2 \| $50 paid \| $500 / month \|" | https://developers.openai.com/api/docs/guides/rate-limits |
| L1c | Automatic tier graduation | "As your spend on our API goes up, we automatically graduate you to the next usage tier." | https://developers.openai.com/api/docs/guides/rate-limits |
| L2 | gpt-5.6-sol Tier 1 limits (no Free row listed) | "\| Tier 1 \| 500 \| 500,000 \| 1,500,000 \|" | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
| L3 | Rate-limit headers include Retry-After and x-ratelimit-* | "\| Retry-After \| 56 \| The minimum number of seconds to wait before retrying a temporary rate-limit error, when present. \|" | https://developers.openai.com/api/docs/guides/rate-limits |
| L3b | Retry-After does not make billing errors retryable | "It does not mean that quota, billing, or other errors that require user action can be resolved by retrying." | https://developers.openai.com/api/docs/guides/rate-limits |
| L4 | slow_down can happen within RPM/TPM | "A `slow_down` error can occur even when your traffic is within its requests-per-minute and tokens-per-minute limits." | https://developers.openai.com/api/docs/guides/rate-limits |
| L5 | Streaming: errors after stream start arrive as events; do not auto-replay | "For streaming requests, these HTTP error responses apply before the stream starts. An error after streaming begins can arrive as a stream event; don't automatically replay a request after consuming output." | https://developers.openai.com/api/docs/guides/rate-limits |
| L6 | Recommended retry policy | "If it's missing or invalid, fall back to exponential backoff with jitter. Limit both the number of attempts and the total time spent retrying. If you manage retries in your application, disable SDK retries or account for them in those limits so nested retry loops don't multiply requests. Don't retry quota, billing, or other errors that require you to take action." | https://developers.openai.com/api/docs/guides/rate-limits |
| L7 | Limits are org + project level, not per end user | "Rate limits are defined at the [organization level](https://developers.openai.com/api/docs/guides/production-best-practices) and at the project level, not user level." | https://developers.openai.com/api/docs/guides/rate-limits |
| L8 | Failed requests still count toward per-minute limits | "Note that unsuccessful requests contribute to your per-minute limit, so continuously resending a request won’t work." | https://developers.openai.com/api/docs/guides/rate-limits |
| L9 | OpenAI recommends per-end-user usage caps | "To protect against automated and high-volume misuse, set a usage limit for individual users within a specified time frame (daily, weekly, or monthly)." | https://developers.openai.com/api/docs/guides/rate-limits |

## 4. Python SDK source (openai 3.14.0, installed in this folder's .venv)

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| P1 | Installed SDK version (= PyPI latest, uploaded 2026-09-14) | "Version: 3.14.0" | https://pypi.org/project/openai/ |
| P2 | Default retries = 2 | "DEFAULT_MAX_RETRIES = 2" | openai/_constants.py |
| P2b | README: which errors are retried | "Certain errors are automatically retried 2 times by default, with a short exponential backoff. Connection errors (for example, due to a network connectivity problem), 408 Request Timeout, 409 Conflict, 429 Rate Limit, and >=500 Internal errors are all retried by default." | https://github.com/openai/openai-python#retries |
| P3 | Retry decision: x-should-retry header wins; else any 429 retried (so spend-limit 429s are retried unless the server sends x-should-retry: false — header behavior undocumented) | "# If the server explicitly says whether or not to retry, obey." | openai/_base_client.py _should_retry |
| P4 | Backoff constants; Retry-After honored up to 120 s, larger values stop retries | "INITIAL_RETRY_DELAY = 0.5 MAX_RETRY_DELAY = 8.0 MAX_RETRY_AFTER_DELAY = 2 * 60" | openai/_constants.py |
| P5 | Default timeout 600 s total, 5 s connect; timeouts are retried | "DEFAULT_TIMEOUT = httpx2.Timeout(timeout=600, connect=5.0)" | openai/_constants.py |
| P5b | README timeout wording | "By default requests time out after 10 minutes." | https://github.com/openai/openai-python#timeouts |
| P6 | Stream consumption not retried | "Stream consumption is not automatically retried, because replaying a request could duplicate output already delivered to your application." | https://github.com/openai/openai-python#handling-errors |
| P7 | responses.stream(...).get_final_response() raises if the stream ended failed/incomplete | "raise RuntimeError("Didn't receive a `response.completed` event.")" | openai/lib/streaming/responses/_responses.py |
| P8 | Error body fields exposed on exceptions (code/param/type) + request_id | "self.request_id = response.headers.get("x-request-id")" | openai/_exceptions.py |

## 5. Refusals, incomplete responses, moderation, safety identifiers

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| R1 | Refusal = content part type "refusal" inside an output message | "- `ResponseOutputRefusal object { refusal, type }` A refusal from the model. - `refusal: string` The refusal explanation from the model. - `type: "refusal"`" | https://developers.openai.com/api/reference/resources/responses/methods/create |
| R2 | Structured outputs: refusal field instead of schema | "Since a refusal does not necessarily follow the schema you have supplied in `response_format`, the API response will include a new field called `refusal` to indicate that the model refused to fulfill the request." | https://developers.openai.com/api/docs/guides/structured-outputs |
| R2b | Streaming refusal events | "## response.refusal.done Emitted when refusal text is finalized." | https://developers.openai.com/api/reference/resources/responses/streaming-events |
| R3 | max_output_tokens: status incomplete, may produce no visible text but still bill | "If the generated tokens reach the context window limit or the `max_output_tokens` value you've set, you'll receive a response with a `status` of `incomplete` and `incomplete_details` with `reason` set to `max_output_tokens`. This might occur before any visible output tokens are produced, meaning you could incur costs for input and reasoning tokens without receiving a visible response." | https://developers.openai.com/api/docs/guides/reasoning |
| R3b | Suggested starting reserve | "OpenAI recommends reserving at least 25,000 tokens for reasoning and outputs when you start experimenting with these models." | https://developers.openai.com/api/docs/guides/reasoning |
| R4 | Incomplete reasons enum | "`reason: optional "max_output_tokens" or "max_messages" or "content_filter" or "steered"`" | https://developers.openai.com/api/reference/resources/responses/methods/create |
| R5 | Response status enum | "The status of the response generation. One of `completed`, `failed`, `in_progress`, `cancelled`, `queued`, or `incomplete`." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| R6 | Moderation endpoint is free; inline moderation in Responses; scores are signals, not auto-block; tool outputs are scored | "Treat moderation scores as signals for your application's policy, not as an automatic blocking decision." | https://developers.openai.com/api/docs/guides/moderation |
| R6b | Free | "The moderation endpoint is free to use, and image files can be up to 20 MB." | https://developers.openai.com/api/docs/guides/moderation |
| R6c | Inline moderation covers tool outputs (white-paper text would be scored) | "For tool-calling requests, moderation covers tool-call arguments and tool outputs when they appear in conversation content." | https://developers.openai.com/api/docs/guides/moderation |
| R6d | Moderation recommended (not mandated) in safety best practices | "OpenAI's [Moderation API](https://developers.openai.com/api/docs/guides/moderation) is free-to-use and can help reduce the frequency of unsafe content in your completions." | https://developers.openai.com/api/docs/guides/safety-best-practices |
| R7 | safety_identifier: recommended, not required; hash; session ID for logged-out previews | "If you offer a preview of your product to non-logged in users, you can send a session ID instead. Safety identifiers are recommended for products where individual users interact with a model, but they are not required." | https://developers.openai.com/api/docs/guides/safety-best-practices |
| R7b | Max length 64 | "The IDs should be a string that uniquely identifies each user, with a maximum length of 64 characters." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| R7c | Per-identifier blocking (format of error not specified) | "The safety identifier receives an `identifier blocked` error on all future GPT-5 requests for the same identifier. OpenAI cannot currently unblock an individual identifier." | https://developers.openai.com/api/docs/guides/safety-checks |
| R7d | Old `user` field is being replaced | "This field is being replaced by `safety_identifier` and `prompt_cache_key`." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| R8 | Without safety_identifier, cyber safeguards may cut off the whole org | "If your organization has not implemented a per-user [safety_identifier](https://developers.openai.com/api/docs/guides/safety-best-practices#implement-safety-identifiers), access may be temporarily revoked for the **entire organization**." | https://developers.openai.com/api/docs/guides/safety-checks/cybersecurity |
| R8b | cyber_policy error code | "In this case, API requests will return an error with the error code `cyber_policy`." | https://developers.openai.com/api/docs/guides/safety-checks/cybersecurity |
| R9 | Misalignment block = 403 misalignment_policy_violation; do not retry | "When misalignment monitoring blocks a request before streaming begins, the API returns HTTP `403`, with error type `invalid_request_error` and code `misalignment_policy_violation`." | https://developers.openai.com/api/docs/guides/safety-checks/misalignment-monitoring |
| R10 | GPT-5.6 real-time classifiers can block/refuse and pause streams | "When using GPT-5.6 models, users may encounter safeguards that block or refuse some requests due to real-time cyber and biology misuse classifiers that are run as model outputs are generated. Other requests may take longer because generation is paused for several seconds mid-stream while these classifiers synchronously review outputs." | https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6 |
| R11 | Org-level escalation for repeated high-risk traffic | "If the requests continue past the stated time threshold (usually seven days), we stop your org's access to GPT-5. Requests will no longer work." | https://developers.openai.com/api/docs/guides/safety-checks |
| R12 | Safety best practices relevant to an anonymous demo | "Limiting the amount of text a user can input into the prompt helps avoid prompt injection. Limiting the number of output tokens helps reduce the chance of misuse." | https://developers.openai.com/api/docs/guides/safety-best-practices |
| R12b | KYC is recommended (demo is anonymous -> deviation) | "Users should generally need to register and log-in to access your service." | https://developers.openai.com/api/docs/guides/safety-best-practices |
| R13 | Streaming makes moderation harder | "Note that streaming the model's output in a production application makes it more difficult to moderate the content of the completions, as partial completions may be more difficult to evaluate. This may have implications for approved usage." | https://developers.openai.com/api/docs/guides/streaming-responses |

## 6. Data controls

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| D1 | API data not used for training by default | "As of March 1, 2023, data sent to the OpenAI API is not used to train or improve OpenAI models (unless you explicitly opt in to share data with us)." | https://developers.openai.com/api/docs/guides/your-data |
| D2 | Abuse monitoring logs up to 30 days (store=false does not change this) | "By default, abuse monitoring logs are generated for all API feature usage and retained for up to 30 days, unless longer retention is required by law, or is reasonably necessary to protect our services or any third party from harm." | https://developers.openai.com/api/docs/guides/your-data |
| D3 | store defaults to true -> stored at least 30 days | "Defaults to true when omitted. If set to true, response data will be stored for at least 30 days, subject to the [data retention exceptions](/api/docs/guides/your-data#v1responses)." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| D3b | Stored responses visible in dashboard logs; disable with store=false | "Response objects are saved for 30 days by default. They can be viewed in the dashboard [logs](https://platform.openai.com/logs?api=responses) page or [retrieved](https://developers.openai.com/api/reference/resources/responses/methods/retrieve) via the API. You can disable this behavior by setting `store` to `false` when creating a Response." | https://developers.openai.com/api/docs/guides/conversation-state |
| D4 | store=false: reasoning items carry encrypted_content by default; include flag is legacy | "When you create a response in stateless mode, reasoning items in the response's `output` array include an `encrypted_content` property by default. Stateless mode applies when `store` is `false` or when your organization uses Zero Data Retention (ZDR). The API still accepts the legacy `reasoning.encrypted_content` value in `include` for compatibility, but doesn't require it." | https://developers.openai.com/api/docs/guides/reasoning |
| D4b | Tool loops: pass reasoning + function_call items back | "If the model calls multiple functions consecutively, you should pass back all reasoning items, function call items, and function call output items, since the last `user` message." | https://developers.openai.com/api/docs/guides/reasoning |
| D4c | GPT-5.6 + store=false: replay encrypted reasoning items | "For `store: false` or Zero Data Retention, replay the encrypted reasoning items that the API returns by default." | https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6 |
| D4d | When streaming, take encrypted_content from output_item.done | "When streaming, use the completed reasoning item and its `encrypted_content` from the `response.output_item.done` event in subsequent requests." | https://developers.openai.com/api/reference/resources/responses/methods/create |
| D5 | ZDR / Modified Abuse Monitoring need prior approval | "Currently, these controls are subject to prior approval by OpenAI and acceptance of additional requirements." | https://developers.openai.com/api/docs/guides/your-data |
| D6 | Prompt caching may keep encrypted KV tensors up to 24 h | "Prompt caching may store encrypted key/value tensors in GPU-local storage as application state. This data is stored on the local GPU machines and is not retained after the 24-hour expiration." | https://developers.openai.com/api/docs/guides/your-data |
| D7 | Moderations endpoint: no abuse-monitoring or app-state retention | "\| `/v1/moderations` \| No \| None \| None \| Yes \| No \|" | https://developers.openai.com/api/docs/guides/your-data |

## 7. API key security

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| K1 | Never expose key client-side; load from env/KMS on server | "**Remember that your API key is a secret.** Don't share it with others or expose it in any client-side code such as browsers or apps. Load API keys from an environment variable or key management service on the server." | https://developers.openai.com/api/reference/overview |
| K2 | Route requests through your backend | "Requests should always be routed through your own backend server where you can keep your API key secure." | https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety |
| K3 | Set key expiration + rotation | "We strongly recommend setting an expiration date when you create a project API key and establishing a regular key rotation process." | https://developers.openai.com/api/docs/guides/production-best-practices |
| K4 | Revocation is fast | "Revocations of an API key take effect within a few seconds." | https://developers.openai.com/api/reference/overview |
| K5 | Log request IDs | "**OpenAI recommends logging request IDs in production deployments**" | https://developers.openai.com/api/reference/overview |
| K6 | IP allowlist needs fixed egress; failure = 401 ip_not_authorized | "Use an IP allowlist as another layer of protection for production workloads with fixed or well-defined network egress." | https://developers.openai.com/api/docs/guides/ip-allowlist |
| K6b | Allowlist failure code | "From an IP address that is not included in the active allowlist, the request fails with HTTP `401` and the `ip_not_authorized` error code." | https://developers.openai.com/api/docs/guides/ip-allowlist |

## 8. Terms relevant to a public anonymous demo

| ID | Claim | Exact quote | URL |
|---|---|---|---|
| T1 | Services Agreement governs API use by developers | "This OpenAI Services Agreement only applies to use of OpenAI’s APIs, ChatGPT Enterprise, ChatGPT Business, ChatGPT for Clinicians, and other services for customers who are businesses and developers" | https://openai.com/policies/services-agreement/ |
| T2 | Allowed to offer an app to End Users | "This includes the right to use OpenAI’s API to integrate the Services into Customer Applications and to make Customer Applications available to End Users." | https://openai.com/policies/services-agreement/ |
| T3 | Developer is responsible for End Users' activity | "Customer is responsible for all activities that occur under its Account, including the activities of End Users with an End User Account or who access the Services through a Customer Application." | https://openai.com/policies/services-agreement/ |
| T4 | Supported countries restriction (South Korea is on the list) | "Customer and End Users may not access or offer access to the Services outside of the Supported Countries and Territories." | https://openai.com/policies/services-agreement/ |
| T5 | Restrictions incl. minors, key transfer, circumventing limits | "(c) allow minors to use OpenAI Services without consent from their parent or guardian;" | https://openai.com/policies/services-agreement/ |
| T5b |  | "(g) buy, sell, or transfer API keys from, to, or with a third party; (h) interfere with or disrupt the Services, including circumvent any rate limits or restrictions or bypass any protective measures or safety mitigations for the Services;" | https://openai.com/policies/services-agreement/ |
| T6 | Usage Policies apply (effective Oct 29, 2025) | "Your use of OpenAI services must follow these Usage Policies:" | https://openai.com/policies/usage-policies/ |
| T7 | Demos allowed; label AI-generated content | "Indicate that the content is AI-generated in a way no user could reasonably miss or misunderstand." | https://openai.com/policies/sharing-publication-policy/ |
| T8 | Under-18 extra duties if minors are served | "You should not use OpenAI services to process any personal data of children under 13 or the applicable age of digital consent without first implementing zero data retention in our API." | https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance |

## 9. Live API call record (the only call made)

| Call | Model | Billed? | Result |
|---|---|---|---|
| GET /v1/models via SDK 3.14.0 (max_retries=0), key read from .env inside script, never printed | n/a | Not a generation call; no token usage; cost $0 | HTTP 200; visible: gpt-5.6-sol=True, gpt-5.6=False, gpt-5.6-terra=True, gpt-5.6-luna=True, omni-moderation-latest=True; 132 models; no `x-ratelimit-*` or `openai-project` headers on this endpoint |

## 10. Recommended safeguard setup (derived from the rows above; values marked "pick" are choices, not doc facts)

| Layer | Setting | Based on |
|---|---|---|
| Billing | Prepay at least $5 (Tier 1: org usage cap $100/month). If dev + evals + public may exceed $100 in September, prepay $50 (Tier 2: $500/month) so `organization_usage_limit_exceeded` cannot hit mid-demo. | L1, L1b, S4 |
| Organization | Monthly spend limit = sum of project limits, **Enforce a hard limit ON**, plus spend alerts. Backstop only. | S1, S1b, S2b, S5 |
| Project `public` (HF Space only) | Monthly limit pick $12 (below the $14 budget because enforcement can overshoot), hard limit ON, alerts at pick 50% / 80%. Model allowlist: `gpt-5.6-sol` (+ `omni-moderation-latest` if the allowlist also gates moderations — unknown). Lower project RPM/TPM for gpt-5.6-sol (pick e.g. 30 RPM / 300k TPM). Dedicated key with an expiration date, stored only as an HF Space Secret. | S3, S5b, S7, S8, S9, K1, K3 |
| Project `dev` | Hard limit pick $60 first month, own key in the local `.env` (gitignored). Evals and example-gallery pre-runs bill here, not to `public`. | S7, S5b |
| App (still required) | Per-visitor and daily caps from spec 6.3 stay: hard limits are monthly and delayed, and OpenAI recommends per-user caps. | S3, L9 |
| Request | `store=False`; replay all output items (incl. encrypted reasoning) in the tool loop; `safety_identifier` = sha256(salt + visitor hash) (64 hex chars); explicit `max_output_tokens`; input length cap (300 chars already in spec). | D2-D4d, R7, R7b, R8, R12 |
| Moderation | Call the free `/v1/moderations` on the visitor question only; block only chosen categories; log the rest. Don't use inline moderation on the whole request (it scores tool outputs = white-paper text about war/nuclear issues). | R6-R6d, D7 |
| Client | `max_retries=0` + app retry (max 2) only for 429 non-billing / 5xx / 503 / timeout / connection, only before any streamed output, honoring `Retry-After` (give up if too long). Explicit timeout (SDK default 600 s and timeouts are retried twice). | E3, L5, L6, P2-P6 |
| Stream | Iterate events; treat `response.failed`, `response.incomplete`, `error`, `response.refusal.done` explicitly; don't rely on `get_final_response()` (raises when no `response.completed`). Log `x-request-id` / `request_id`. | L5, P7, P8, R2b, K5 |
| UI | Label answers as AI-generated; add a way to report problems; show "not for minors without guardian" note (pick wording). | T7, R12, T5, T8 |
| Spec change | Claude "server-side fallbacks on refusal" has no OpenAI equivalent in the pages read → refusal/`safety_stop` becomes a Korean message (see `error_handling_sketch.py`). | R1, R9, R10 |

## 11. Inferred (not directly stated in docs)

- The SDK retries **every** 429 unless the server sends `x-should-retry: false`, so spend-limit 429s are probably retried twice (~0.5 s + ~1 s backoff) before surfacing. Whether OpenAI sends that header on billing 429s is undocumented. (P3, P4)
- Worst-case hang with SDK defaults: 600 s timeout x 3 attempts. (P2b, P5, P5b)
- `gpt-5.6-sol` is not rate-limited for the Free tier (its table starts at Tier 1). Model visibility in `/v1/models` (seen for this key) does not prove non-zero limits. (L2, section 9)
- HF Spaces egress IPs are not fixed, so IP allowlisting is impractical for the public key. (K6)
- With GPT-5.6 default `reasoning.context=all_turns` and manual replay, requests may count as "persisted reasoning" for misalignment monitoring; our tools are read-only so blocks should be rare, but 403 `misalignment_policy_violation` must still be handled. (R9, D4c)
- Rejected 429/403 requests are probably not billed (no statement found); `incomplete` responses are billed (R3).
- Usage Policies' ban on "national security or intelligence purposes without our review and approval" should not cover Q&A over public diplomatic white papers, but this is a reading, not a ruling. (T6)

## 12. Unknowns (not found in official pages read)

- Size of hard-limit overshoot / propagation time; whether the "monthly cycle" is calendar month UTC; any minimum limit amount. (S3, S6)
- Headers (`x-should-retry`, `Retry-After`) on billing 429s.
- HTTP status and `error.code` for the `identifier blocked` error; HTTP status of `cyber_policy` / `bio_policy`. (R7c, R8b, E6)
- Behavior of inline moderation `policy.mode: "block"` (enum only) and whether inline moderation is billed. (R6)
- When `incomplete_details.reason = "content_filter"` occurs for GPT-5.6 (only enum + a C# sample). (R4)
- Whether the project model allowlist also gates `/v1/moderations`.
- The user's current usage tier, and whether the `.env` key is a project key / which project (the models endpoint returned no project header).
- Prepaid billing details (auto-recharge, credit expiry): `help.openai.com` articles 8264644 and 6614457 returned a Cloudflare challenge (curl) and HTTP 403 (WebFetch) → not read; only a search snippet was seen, so nothing from them is in the table.
- How to honor the Supported-Countries clause (T4) for a globally reachable anonymous Space.

