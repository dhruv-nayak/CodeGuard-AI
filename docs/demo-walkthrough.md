# CodeGuard AI — 5-minute demo walkthrough

Use a disposable local or staging environment and synthetic sample code only.

1. **Create an account and sign in.** Explain that review history is account-scoped.
2. **Run a direct code review.** Load `demo/samples/python_example.py`, choose Python, and review the static findings and test suggestions. Explain that submitted code is not executed.
3. **Compare a second language.** Load `demo/samples/javascript_example.js` and select JavaScript. Explain that non-Python checks are heuristic patterns.
4. **Review repository intelligence.** Use a public test repository or a dedicated fixture repository with a read-only token. Show source findings, dependency advisory status and the CycloneDX SBOM download.
5. **Track remediation.** Change a finding's state and add a short remediation note. Explain that remediation is associated with the saved scan finding.
6. **Export a report.** Download a CSV or PDF report and treat it as sensitive security information.
7. **Close with limitations.** Explain false positives/negatives, bounded scans, exact-version dependency lookup and that a heuristic risk score is not a compliance certification.

Do not use real production credentials or confidential repository source code during a public portfolio demonstration.
