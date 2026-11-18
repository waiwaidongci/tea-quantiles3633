Schema v1 is defined by the SQLAlchemy models and created at startup via Base.metadata.create_all. For this local small application no destructive migration is run. Back up named db-data before modifying schemas.

复测单表（retest_studies / retest_samples / retest_claims / retest_drafts(+items) / retest_lists(+items) / retest_meta）同属 schema v1，启动时 create_all 幂等建表，不影响既有数据。
