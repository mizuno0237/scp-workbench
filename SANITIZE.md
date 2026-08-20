# Public vs internal

This GitHub repo is a **synthetic planning sample**.

**Never publish**

- Customer plant names, live BOM, or real demand
- Internal Java / GitLab services
- A `--mirror` of a product suite

**OK to publish**

- Fictional plant + BOM + weekly demand
- Demand → MPS → capacity load
- Module names (MPS / MDS / DCP / ODS) as an interview map

**Scan before every push**

```bash
python scripts/scan-secrets.py
```
