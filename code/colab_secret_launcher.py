"""Explicitly authorized Colab HF_TOKEN read; never execute merely on import."""
import gc
import json
import drive_wrapper


def launch_from_colab_secrets(continuation_args):
    """Call only after user grants this notebook HF_TOKEN access and execution."""
    token = None
    try:
        # Reject custom mirrors BEFORE asking Colab for the secret.
        drive_wrapper.require_official_hf_endpoint()
        if (not isinstance(continuation_args,(list,tuple)) or not all(isinstance(x,str) for x in continuation_args)
            or any(x in continuation_args for x in ("--preflight-only","--validate-input-only"))
            or continuation_args.count("--judge") != 1 or continuation_args[continuation_args.index("--judge")+1:] [:1] != ["LG"]):
            raise ValueError("launcher requires explicit full159 LG stage arguments")
        # Verifies code, input, old-HB lineage, current GPU/packages, and Drive
        # write/read/hash before requesting the secret; no model is downloaded.
        if drive_wrapper.main([*continuation_args,"--preflight-only"]) != 0:
            print(json.dumps({"status":"preflight_failed","secret_read":False}))
            return 1
        drive_wrapper.require_official_hf_endpoint()
        from google.colab import userdata
        token = userdata.get("HF_TOKEN")
        if not isinstance(token,str) or not token:
            raise ValueError("HF_TOKEN is unavailable")
        result = drive_wrapper.main(continuation_args,auth_token=token)
        print(json.dumps({"full159_lg_exit_code":result}))
        return result
    except BaseException as exc:
        print(json.dumps({"status":"stopped","exception_type":drive_wrapper.safe_exception_name(exc,token)}))
        return 1
    finally:
        token = None
        gc.collect()
        # Dropping references is not guaranteed memory zeroization.


def launch_hb_without_secret(stage_args):
    """HB stage never reads or forwards credentials; fp16 scope validated by wrapper."""
    try:
        if (not isinstance(stage_args,(list,tuple)) or not all(isinstance(x,str) for x in stage_args)
            or stage_args.count("--judge")!=1 or stage_args[stage_args.index("--judge")+1:][:1] != ["HB"]):
            raise ValueError("explicit full159 HB stage arguments required")
        if drive_wrapper.main([*stage_args,"--preflight-only"]) != 0:
            return 1
        return drive_wrapper.main(stage_args)
    except BaseException as exc:
        print(json.dumps({"status":"stopped","exception_type":drive_wrapper.safe_exception_name(exc)}))
        return 1
