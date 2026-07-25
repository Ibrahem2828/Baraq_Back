# Baraq AI evaluation

Every production prompt/model combination must be evaluated against a versioned,
human-reviewed dataset before deployment. Required phase-one gates:

- Fahes: schema validity, single correct answer, source grounding, duplicate rate,
  teacher quality score, difficulty calibration.
- Khota: daily time-limit compliance, date validity, task feasibility, adherence.
- Rasheed: numerical faithfulness, actionability, absence of unsupported claims.

A user rating is only a signal. It never becomes ground truth or a deployable
fine-tuning example without anonymization and human approval.
