# Audit Workpaper — IT General Controls - Change Management

**Period:** 2026-07-01 to 2026-09-30  
**Prepared:** 2026-10-19 21:09 by audit-evidence-agent (AI-assisted, requires reviewer sign-off)

## 1. Test summary

| Control | Population tested | Exceptions | Result |
|---|---:|---:|---|
| CM-01 | 30 | 2 | Exceptions noted |
| CM-02 | 30 | 2 | Exceptions noted |
| CM-03 | 30 | 1 | Exceptions noted |
| CM-04 | 3 | 2 | Exceptions noted |
| CM-05 | 32 | 2 | Exceptions noted |

## 2. Findings

### Finding 1: Changes deployed without timely authorization  `High`

- **Control:** CM-01
- **Condition:** 2 of 30 items failed: CHG-1007 (Approved 26.0h AFTER deployment (2026-07-24 00:00 vs 2026-07-22 22:00)); CHG-1012 (No approver / approval timestamp on ticket)
- **Criteria:** Standard changes must be approved before deployment; emergency changes approved within 2 business days.
- **Effect / risk:** Unauthorized changes to financially significant systems could affect the integrity of financial data.
- **Recommendation:** Enforce a workflow gate that blocks deployment until the ticket is in 'Approved' status; review exceptions with change owners.
- **Evidence references:** CHG-1007, CHG-1012

### Finding 2: Segregation of duties conflicts in change process  `High`

- **Control:** CM-02
- **Condition:** 2 of 30 items failed: CHG-1015 (m.das deployed own change to production); CHG-1030 (j.thomas approved own change)
- **Criteria:** Developers must not approve or deploy their own changes.
- **Effect / risk:** A single individual could introduce and promote unreviewed code to production.
- **Recommendation:** Restrict production deployment rights to the release team and block self-approval in the ticketing tool.
- **Evidence references:** CHG-1015, CHG-1030

### Finding 3: Production deployments not traceable to approved change tickets  `High`

- **Control:** CM-05
- **Condition:** 2 of 32 items failed: DEP-5031 (Deployment to PaymentsAPI by r.iyer at 2026-08-14 23:41 has no change ticket); DEP-5032 (References CHG-9999, which does not exist in the change system)
- **Criteria:** Every production deployment must reference a valid approved change ticket.
- **Effect / risk:** Unauthorized changes reached production outside the change process.
- **Recommendation:** Integrate the CI/CD pipeline with the change system to reject deployments without a valid ticket; investigate the listed deployments.
- **Evidence references:** DEP-5031, DEP-5032

### Finding 4: Test / UAT evidence not retained  `Medium`

- **Control:** CM-03
- **Condition:** 1 of 30 items failed: CHG-1019 (No test or UAT evidence attached)
- **Criteria:** Test and user acceptance evidence must be attached before deployment.
- **Effect / risk:** Untested changes may cause processing errors or outages.
- **Recommendation:** Make the UAT sign-off attachment a mandatory field before approval.
- **Evidence references:** CHG-1019

### Finding 5: Emergency changes lacking timely post-implementation review  `Medium`

- **Control:** CM-04
- **Condition:** 2 of 3 items failed: CHG-1022 (Emergency change has no post-implementation review); CHG-1026 (PIR completed 5 business days after deployment)
- **Criteria:** Emergency changes require a PIR within 2 business days.
- **Effect / risk:** Emergency changes bypass normal controls; without PIR, inappropriate changes may go undetected.
- **Recommendation:** Auto-create a PIR task with a 2-business-day SLA for every emergency change and report breaches to the CAB.
- **Evidence references:** CHG-1022, CHG-1026

## 3. Exception detail

- **CM-01 / CHG-1007** — approved before deployment: Approved 26.0h AFTER deployment (2026-07-24 00:00 vs 2026-07-22 22:00)
- **CM-01 / CHG-1012** — approver recorded: No approver / approval timestamp on ticket
- **CM-02 / CHG-1015** — developer != deployer: m.das deployed own change to production
- **CM-02 / CHG-1030** — developer != approver: j.thomas approved own change
- **CM-03 / CHG-1019** — test / UAT evidence attached: No test or UAT evidence attached
- **CM-04 / CHG-1022** — PIR recorded: Emergency change has no post-implementation review
- **CM-04 / CHG-1026** — PIR within 2 business days: PIR completed 5 business days after deployment
- **CM-05 / DEP-5031** — deployment has ticket reference: Deployment to PaymentsAPI by r.iyer at 2026-08-14 23:41 has no change ticket
- **CM-05 / DEP-5032** — ticket exists: References CHG-9999, which does not exist in the change system

## 4. Conclusion

Change management controls are NOT operating effectively for the period: 5 findings were identified, including unauthorized production deployments and segregation of duties conflicts. Management should remediate and the audit team should perform follow-up testing next quarter.
