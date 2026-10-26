# Project A - Weekly Status Reports

Reports are written by the delivery lead every Friday.

## Week 1

**Progress:** Kick-off complete. Repositories created, CI pipeline running, design system approved.

**Risks and issues:** Core banking API sandbox access is delayed by a week.

**Metrics:** Stories done: 8

## Week 2

**Progress:** Identity Service skeleton deployed to development. First login works end to end.

**Risks and issues:** Security wants shorter token lifetimes; discussion scheduled.

**Metrics:** Stories done: 14

## Week 3

**Progress:** Staging environment up. For load testing, the access token lifetime was temporarily raised to 30 minutes in staging only. Production design remains 15 minutes.

**Risks and issues:** Staging database is smaller than production, so load results need scaling.

**Metrics:** Stories done: 17

## Week 4

**Progress:** Account and Transaction services feature complete. Statement worker prototype demonstrated.

**Risks and issues:** Categorisation model endpoint is unstable.

**Metrics:** Stories done: 21

## Week 5

**Progress:** Card freeze flow working against the processor sandbox. Accessibility audit of the login and account pages started.

**Risks and issues:** Processor sandbox does not reproduce production timeouts.

**Metrics:** Stories done: 19

## Week 6

**Progress:** Dispute Service and attachment scanning completed. Messaging Service in review.

**Risks and issues:** Two accessibility defects open on the transactions page.

**Metrics:** Stories done: 23

## Week 7

**Progress:** Staging authentication regression test found defect DEF-231: the gateway cached the previous signing secret for 5 minutes instead of 20. Beta date moved by one month to allow a fix and retest.

**Risks and issues:** DEF-231 blocks beta. Platform team assigned.

**Metrics:** Stories done: 16

## Week 8

**Progress:** DEF-231 fixed and verified. Load test at 5000 concurrent users passed with 1.4 second p95 latency.

**Risks and issues:** Penetration test booking slipped to November.

**Metrics:** Stories done: 25

## Week 9

**Progress:** Beta started with 150 staff users. Notification retries tuned after observing dead-letter growth.

**Risks and issues:** SMS provider receipts are slow.

**Metrics:** Stories done: 22

## Week 10

**Progress:** Beta feedback positive. Satisfaction score 4.3 out of 5. Preparing launch checklist and runbook rehearsal.

**Risks and issues:** Statement month-end load needs a pre-scaling rule.

**Metrics:** Stories done: 20

