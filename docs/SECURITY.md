# Security model
- Organization ID is never accepted from request bodies for scoped resources; it comes from a signed access token.
- Every scoped lookup uses both resource ID and tenant ID. Child creation first verifies the parent under the same tenant.
- Membership is rechecked on every request, so access is revoked immediately even before JWT expiry.
- Roles: OWNER/ADMIN manage organization resources; QA creates targets/runs; VIEWER is read-only.
- Refresh tokens are random, hashed at rest, rotated on use, and revocable. Target credentials are Fernet-encrypted.
- Browser target URLs are SSRF-checked. Private/loopback targets are denied by default.
- For PostgreSQL production, add RLS as defense in depth and use a KMS/Vault for encryption keys.
