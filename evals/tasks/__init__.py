from evals.tasks.login_script import run as login_script
from evals.tasks.archive_restore import run as archive_restore
from evals.tasks.vc_pr_flow import run as vc_pr_flow
from evals.tasks.uts_rename import run as uts_rename
from evals.tasks.global_param import run as global_param

TASKS = {
    "login_script": login_script,
    "archive_restore": archive_restore,
    "vc_pr_flow": vc_pr_flow,
    "uts_rename": uts_rename,
    "global_param": global_param,
}
