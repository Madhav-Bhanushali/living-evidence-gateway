"""Run the real standalone compiler on fictional data. No model or network."""
from dataclasses import replace
import copy
import json
from .fixtures import example_system
from .core import GatewayError

def run():
    compiler,store,scope,policy,required=example_system()
    receipt=compiler.compile(scope,policy,required)
    compiler.verify(receipt,scope,policy)
    steps=[{"title":"Compile the least-disclosure sufficient bundle",
            "receipt":receipt,"verified":True}]
    tampered=copy.deepcopy(receipt)
    tampered["claims"]["order/42.status"]="invented"
    try:
        compiler.verify(tampered,scope,policy)
        tamper_blocked=False
    except GatewayError:
        tamper_blocked=True
    steps.append({"title":"Mutate a signed claim","tampering_rejected":tamper_blocked})
    store.revoke("status_primary")
    try:
        compiler.verify(receipt,scope,policy)
        revoked_blocked=False
    except GatewayError:
        revoked_blocked=True
    steps.append({"title":"Revoke the original witness","old_receipt_rejected":revoked_blocked})
    repaired=compiler.rebase(receipt,scope,policy)
    compiler.verify(repaired,scope,policy)
    steps.append({"title":"Repair the witness without changing the claims",
                  "receipt":repaired,"claims_unchanged":repaired["claims"]==receipt["claims"],
                  "verified":True})
    # Remove old alternatives and update the only status witness.
    store.revoke("broad_record")
    replica=store.get("status_replica")
    store.put(replace(replica,version="v2",facts={"order/42.status":"returned"}))
    try:
        compiler.rebase(repaired,scope,policy)
        changed_blocked=False
    except GatewayError:
        changed_blocked=True
    steps.append({"title":"Change the source fact","old_answer_rebase_rejected":changed_blocked})
    return {"prototype":"Living Evidence Witness Compiler",
            "scope":"fictional typed claims; not unrestricted natural-language truth",
            "steps":steps,
            "checks_passed":all([tamper_blocked,revoked_blocked,
                                 repaired["claims"]==receipt["claims"],changed_blocked])}

def main():
    result=run()
    print(json.dumps(result,indent=2))
    if not result["checks_passed"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
