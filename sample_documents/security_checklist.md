# Security Checklist

Every story that touches authentication, payment data, or personally identifiable
information must confirm the following before it can be marked done:

1. No secrets, API keys, or credentials are hardcoded or logged.
2. All external API calls use TLS.
3. User-supplied input is validated and never directly interpolated into a database query
   or shell command.
4. Authentication tokens expire and are not stored in plain text.
5. Payment card data is never stored directly — use a PCI-DSS-compliant provider's
   hosted fields or tokenization.
6. Personally identifiable information is encrypted at rest.
7. Access to administrative or configuration endpoints requires authentication and is
   logged with the acting user's identity.
