# Security policy

## Scope

This demo processes uploaded spreadsheets in the current Streamlit session.
It is not an identity, permission, audit, or message-sending service. The
public demo mode is offline and uses synthetic rows.

## Safe usage

- Remove phone numbers, names, order details, credentials, and other
  unnecessary personal data before uploading.
- Keep `COMMERCE_LEAD_ENABLE_REAL_AI` disabled unless the deployment is controlled
  and the configured model provider's retention, residency, and billing rules
  have been reviewed.
- Store `OPENAI_API_KEY` only in the environment or a secret manager. Never
  commit it, put it in a spreadsheet, or paste it into an issue.
- Treat every generated reply as a draft. The application blocks unsafe final
  text and requires explicit human confirmation before a row is labelled
  “可发送”.

## Reporting a vulnerability

Please do not publish exploit details, credentials, or personal data in a
public issue. Use the repository's private security contact or a private
maintainer message with:

1. affected commit/version and deployment mode;
2. a minimal reproduction using synthetic data;
3. impact and any logs that are safe to share.

We will acknowledge a report when practicable, validate it with a regression
test, and document a fix without exposing reporter data. This project does
not promise a production SLA or a bug-bounty program.

## Out of scope

Requests to bypass store controls, automate unsolicited messaging, evade a
platform paywall, or process data without the data owner's permission are not
security features and will not be accepted.
