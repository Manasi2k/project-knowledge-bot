# Project B - Architecture Decision Records

## ADR-001: Use a Django monolith

**Status:** Accepted  
**Date:** 2023-09-12

### Context
The team is five developers who know Python and Django. The system has a single deployable purpose and no need for independent scaling of parts.

### Decision
Build one Django application serving both the web interface and the API.

### Consequences
Deployment and debugging are simple. Scaling is limited to adding virtual machines behind the load balancer.

## ADR-002: Store sessions in Redis

**Status:** Accepted  
**Date:** 2023-09-20

### Context
Supervisors and operatives must be signed out immediately when they leave the company or lose a device.

### Decision
Use server-side sessions in Redis with a 30 minute idle timeout. Do not use JWT.

### Consequences
Revocation is instant. Redis becomes a dependency for sign-in, and failover is manual.

## ADR-003: Immutable movement table

**Status:** Accepted  
**Date:** 2023-10-03

### Context
Auditors need to reconstruct stock positions at any date and operatives sometimes make scanning mistakes.

### Decision
Record every scan as an insert-only row in the movement table. Derive stock_level from movements. Fix errors with compensating movements.

### Consequences
The table grows quickly, about 41 million rows. Reporting queries must use the replica.

## ADR-004: Queue scans offline on the handheld

**Status:** Accepted  
**Date:** 2023-10-17

### Context
Warehouse Wi-Fi has dead spots, and operatives cannot wait for the network.

### Decision
Handhelds store scans locally and upload in order, each with a client-generated identifier.

### Consequences
Duplicate prevention relies on the identifier. Stock levels may lag for up to 30 minutes.

## ADR-005: Support only Code 128 barcodes

**Status:** Accepted  
**Date:** 2023-11-02

### Context
Suppliers use several symbologies, but the existing labels the company prints are all Code 128.

### Decision
Support Code 128 only in release 1. Supplier labels in other formats are relabelled at goods-in.

### Consequences
Goods-in is slightly slower for some suppliers. The scanner configuration is simpler.

## ADR-006: Nightly reporting replica

**Status:** Accepted  
**Date:** 2023-11-15

### Context
Month-end reports were slowing down the scanning API.

### Decision
Run reports against a MySQL replica refreshed continuously, and schedule heavy reports after 22:00.

### Consequences
Reports may be up to 60 seconds behind live data.

## ADR-007: Keep MySQL rather than migrate to PostgreSQL

**Status:** Accepted  
**Date:** 2023-12-04

### Context
The team evaluated PostgreSQL for better JSON support. The company has three experienced MySQL database administrators and no PostgreSQL experience, and the existing backup tooling supports only MySQL.

### Decision
Stay on MySQL 8 for release 1 and revisit when JSON queries become a requirement.

### Consequences
No retraining cost and no migration risk. Some reporting queries are harder to write.

## ADR-008: No cloud services in release 1

**Status:** Accepted  
**Date:** 2024-01-09

### Context
The security policy for the logistics network does not yet allow cloud-hosted components.

### Decision
Run entirely on the existing virtual machine estate and revisit after the policy review.

### Consequences
Capacity is fixed by the virtual machines. Disaster recovery uses the second data centre.

