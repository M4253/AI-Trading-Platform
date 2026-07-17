# Go-Live Checklist

## Paper-only operational go-live

- [ ] All backend tests, dashboard tests, type checks, build, and security checks pass on the release commit.
- [ ] A production deployment has explicit CORS, TLS, central logging, private storage, backup scheduling, and a tested recovery drill.
- [ ] An approved production identity provider is integrated; the local demo login is disabled.
- [ ] The paper-trading validation checklist has been completed and retained.
- [ ] The owner has reviewed the current [readiness report](READINESS_REPORT.md).

## Real-money go-live — intentionally blocked

The following are mandatory and are all currently incomplete. Do not mark this section complete or enable live trading in this repository.

- [ ] Independent security, compliance, and operational review.
- [ ] Approved external secret manager and production identity provider.
- [ ] Controlled real IBKR connectivity, account, order, and recovery verification.
- [ ] Valid broker permissions, credentials, account protection, and owner approval.
- [ ] Extended forward paper-trading results reviewed against risk limits.
- [ ] A separate, explicitly authorised implementation that introduces live execution with kill switches and monitoring.
