"""Unit tests for guard.py. Run: python3 -m unittest  (from this directory)."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import guard  # noqa: E402


def run(cmd, branch="feat/x"):
    return guard.evaluate({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": "."},
                          branch_fn=lambda cwd: branch)[0]


class GuardTests(unittest.TestCase):
    def test_allow_nonprod_read(self):
        self.assertIsNone(run("aws ec2 describe-instances --profile nonprod-developer"))

    def test_allow_pulumi_preview(self):
        self.assertIsNone(run("pulumi preview --stack nonprod"))

    def test_deny_pulumi_up_and_destroy(self):
        self.assertEqual(run("pulumi up --yes"), "deny")
        self.assertEqual(run("cd infra && pulumi --stack nonprod destroy"), "deny")

    def test_deny_serverless_firebase_deploy(self):
        self.assertEqual(run("npx sls deploy --stage prod"), "deny")
        self.assertEqual(run("serverless deploy"), "deny")
        self.assertEqual(run("firebase deploy --only hosting"), "deny")

    def test_deny_aws_prod_write(self):
        self.assertEqual(run("aws ecs update-service --cluster prod-main --service prod-claim-ingest --force-new-deployment"), "deny")
        self.assertEqual(run("aws s3 rm s3://papaya-prod-claim-docs/a.pdf"), "deny")

    def test_allow_aws_prod_name_read_without_profile_rule(self):
        self.assertIsNone(run("aws logs describe-log-groups --log-group-name-prefix /prod/claim-ingest"))

    def test_deny_breakglass(self):
        self.assertEqual(run("aws sts get-caller-identity --profile prod-breakglass"), "deny")

    def test_ask_prod_debug_agent_read(self):
        self.assertEqual(run("aws logs start-query --profile prod-debug-agent --log-group-name /prod/claim/app"), "ask")

    def test_deny_phi_log_group(self):
        self.assertEqual(run("aws logs tail /prod/claim/phi/app --profile prod-debug-agent"), "deny")

    def test_deny_secret_reads(self):
        for c in ("aws secretsmanager get-secret-value --secret-id nonprod-x-y",
                  "aws ssm get-parameter --name /nonprod/x/y --with-decryption",
                  "gcloud secrets versions access latest --secret=foo",
                  "kubectl get secret db -o yaml -n nonprod-claim"):
            self.assertEqual(run(c), "deny", c)

    def test_kubectl_prod_namespace(self):
        self.assertEqual(run("kubectl delete pod x -n prod-claim"), "deny")
        self.assertEqual(run("kubectl --namespace=prod-claim rollout restart deploy/api"), "deny")
        self.assertIsNone(run("kubectl get pods -n prod-claim"))
        self.assertIsNone(run("kubectl delete pod x -n nonprod-claim"))

    def test_git_push_rules(self):
        self.assertEqual(run("git push --force origin feat/x"), "deny")
        self.assertEqual(run("git push origin main"), "deny")
        self.assertEqual(run("git push origin HEAD:main"), "deny")
        self.assertEqual(run("git push", branch="main"), "deny")
        self.assertIsNone(run("git push -u origin feat/x"))

    def test_deny_settings_edit_bash_and_tools(self):
        self.assertEqual(run("sed -i 's/true/false/' .claude/settings.json"), "deny")
        self.assertEqual(run("echo '{}' > .claude/settings.local.json"), "deny")
        self.assertIsNone(run("cat .claude/settings.json"))
        d = guard.evaluate({"tool_name": "Edit", "tool_input": {"file_path": "/r/.claude/settings.json"}})
        self.assertEqual(d[0], "deny")

    def test_mcp_tools(self):
        self.assertIsNone(guard.evaluate({"tool_name": "mcp__papaya-docs__search_docs"})[0])
        self.assertEqual(guard.evaluate({"tool_name": "mcp__papaya-docs__delete_page"})[0], "deny")

    def test_cli_output_format_and_fail_closed(self):
        script = os.path.join(os.path.dirname(__file__), "guard.py")
        ok = subprocess.run([sys.executable, script], input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "pulumi up"}}), capture_output=True, text=True)
        out = json.loads(ok.stdout)["hookSpecificOutput"]
        self.assertEqual((ok.returncode, out["permissionDecision"], out["hookEventName"]), (0, "deny", "PreToolUse"))
        bad = subprocess.run([sys.executable, script], input="not json", capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
