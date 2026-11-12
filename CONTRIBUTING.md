# Contributing to CFR-App

Thank you for helping improve open-source GxP compliance and data protection for the life sciences community!

## How to Contribute

1. **Fork & Branch**: Create a feature branch (`git checkout -b feat/your-feature`).
2. **Preserve 21 CFR Part 11 Controls**: Any new endpoint that mutates regulated `GMP` or `CRITICAL` asset state must record an entry via `record_audit_event(...)` and validate electronic signatures where applicable.
3. **Add Equipment Guides**: Have a validated recipe for a specific analytical instrument (e.g., Waters Empower, Agilent OpenLab, Cytiva Unicorn, Tecan EVO)? Submit a PR to `/docs/`!
4. **Run Verification**:
   - Backend: `cd backend && PYTHONPATH=. .venv/bin/pytest -v`
   - Frontend: `cd frontend && npm run build`

## License
By contributing to `cfr-app`, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
