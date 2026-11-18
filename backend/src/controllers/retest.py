from src.services import retest
# Controllers keep endpoint contracts separate from persistence and calculation.
def state(db,day): return retest.state(db,day)
def compile_draft(db,user,day): return retest.compile_draft(db,user,day)
def publish(db,user,day): return retest.publish(db,user,day)
def claim(db,data,user,day): return retest.claim(db,data,user,day)
def set_quota(db,id,data,user): return retest.set_quota(db,id,data,user)
