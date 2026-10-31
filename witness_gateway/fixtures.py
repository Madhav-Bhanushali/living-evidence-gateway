"""Fictional, bounded fixtures for the standalone research prototype."""
from .core import Scope, EvidenceUnit, Policy, Store, Compiler

def example_system(now=1000):
    scope=Scope("example_company","example_kb","example_app","request-example")
    units=[
        EvidenceUnit("broad_record","example_company","example_kb","orders","v1",
                     {"order/42.status":"dispatched","customer/7.email":"person@example.invalid",
                      "customer/7.region":"north"},("identity","region"),9,now),
        EvidenceUnit("status_primary","example_company","example_kb","orders","v1",
                     {"order/42.status":"dispatched"},("order_status",),2,now),
        EvidenceUnit("status_replica","example_company","example_kb","order_replica","v1",
                     {"order/42.status":"dispatched"},("order_status",),3,now),
        EvidenceUnit("return_policy","example_company","example_kb","policies","v1",
                     {"policy/returns.window_days":14},("return_policy",),1,now),
        EvidenceUnit("irrelevant_region","example_company","example_kb","directory","v1",
                     {"customer/7.region":"north"},("region",),1,now),
        EvidenceUnit("other_company_status","other_company","other_kb","orders","v1",
                     {"order/42.status":"cancelled"},("order_status",),1,now),
    ]
    policy=Policy("example_policy","v1",
                  ("orders","order_replica","policies","directory"),
                  ("order/42.status","policy/returns.window_days",
                   "customer/7.email","customer/7.region"),
                  (("identity","region"),),20,8,3600)
    store=Store(units)
    # Fixed public example key is ONLY a test fixture, never a runtime credential.
    compiler=Compiler(store,b"fictional-example-key-not-for-deployment",clock=lambda:now)
    required=["order/42.status","policy/returns.window_days"]
    return compiler,store,scope,policy,required
